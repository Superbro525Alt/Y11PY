from enum import Enum
import threading, queue, time, bisect, asyncio, math, uuid, json, os, random
from typing import (
    Any,
    Callable,
    Dict,
    Optional,
    List,
    Generic,
    Self,
    Type,
    TypeVar,
    Iterator,
    Set,
    Union,
    overload,
)
from collections import deque, defaultdict
import logging
from dataclasses import dataclass, field
from functools import total_ordering
from util import logger
import datetime


@dataclass
class StateData:
    id: str = field()  # uuid4()
    state: Optional[Any] = field(default=None)
    last_update: float = field(
        default_factory=lambda: datetime.datetime.now().timestamp()
    )


class EventType(Enum):
    UPDATE_STATE = 0


@dataclass
class Event:
    event_type: EventType


T = TypeVar("T")


@total_ordering
@dataclass(order=False)
class Frame(Generic[T]):
    data: T = field(compare=False)

    # The three fields used for ordering.
    available_at: float = field(default_factory=time.time)  # Defaults to current time.
    priority: int = 0  # Default priority.
    id: int = 0  # Default ID (can be overridden by your pipeline logic).

    # Other fields (not used for ordering).
    metadata: Optional[Dict[str, Any]] = field(default=None, compare=False)
    annotations: Dict[str, Any] = field(default_factory=dict, compare=False)
    timestamp: float = field(default_factory=time.time, compare=False)
    sender_id: Optional[str] = field(default=None, compare=False)
    expire_at: Optional[float] = field(default=None, compare=False)
    retry_count: int = field(default=0, compare=False)
    delivered_to: List[str] = field(default_factory=list, compare=False)
    correlation_id: Optional[str] = field(default=None, compare=False)
    topic: Optional[str] = field(default=None, compare=False)
    is_response: bool = field(default=False, compare=False)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Frame):
            return NotImplemented
        return (
            self._safe(self.available_at),
            self._safe(self.priority),
            self._safe(self.id),
        ) == (
            self._safe(other.available_at),
            self._safe(other.priority),
            self._safe(other.id),
        )

    def __lt__(self, other: "Frame[T]") -> bool:
        if not isinstance(other, Frame):
            return NotImplemented
        return (
            self._safe(self.available_at),
            self._safe(self.priority),
            self._safe(self.id),
        ) < (
            self._safe(other.available_at),
            self._safe(other.priority),
            self._safe(other.id),
        )

    @staticmethod
    def _safe(v: Optional[Union[int, float]]) -> Union[int, float]:
        """
        Returns the value if not None, otherwise returns float('-inf').
        With the default values defined above, None is not expected.
        """
        return v if v is not None else float("-inf")


class FramePipeline(Generic[T]):
    """ """

    def __init__(
        self,
        name: str = "FramePipeline",
        maxsize: Optional[int] = 1000,
        use_priority: bool = False,
        enable_delayed_delivery: bool = False,
        auto_purge_interval: Optional[float] = None,
        ack_timeout: Optional[float] = 2.0,
        max_retries: int = 3,
        global_rate_limit: Optional[float] = None,
        metrics_interval: Optional[float] = None,
        encrypt_func: Optional[Callable[[Any], Any]] = None,
        decrypt_func: Optional[Callable[[Any], Any]] = None,
        distributed_forwarder: Optional[Callable[[Frame[T]], None]] = None,
        backpressure_callback: Optional[Callable[[str, int], None]] = None,
        persist_file: Optional[str] = None,
        config_file: Optional[str] = None,
        load_shedding_threshold: Optional[int] = None,
        cluster_mode: bool = False,
        deduplication_window: float = 60.0,
        delivery_timeout: float = 5.0,
    ) -> None:

        self.name = name

        self.maxsize = maxsize
        self.use_priority = use_priority
        self.enable_delayed_delivery = enable_delayed_delivery
        self.sorted_queues = self.use_priority or self.enable_delayed_delivery

        self.queue: queue.Queue[Frame[T]] = queue.Queue(maxsize=maxsize)
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.closed: bool = False
        self.frame_counter: int = 0
        self.sender_id: Optional[str] = None

        if self.sorted_queues:
            self.consumers: Dict[str, List[Frame[T]]] = {}
        else:
            self.consumers: Dict[str, deque] = {}

        self.consumer_filters: Dict[str, Optional[Callable[[Frame[T]], bool]]] = {}
        self.consumer_status: Dict[str, bool] = {}  # True means paused.
        self.consumer_maxsize: Dict[str, Optional[int]] = {}
        self.consumer_overflow_policy: Dict[str, str] = (
            {}
        )  # "drop", "error", or "block"
        self.consumer_rate_limits: Dict[str, float] = {}
        self.consumer_last_receive: Dict[str, float] = {}

        self.metrics: Dict[str, int] = {
            "frames_sent": 0,
            "frames_received": 0,
            "frames_expired": 0,
            "frames_dropped": 0,
            "frames_retried": 0,
            "frames_failed": 0,
            "delivery_timeouts": 0,
        }
        self.consumer_metrics: Dict[str, Dict[str, Union[int, float]]] = {}

        self.delivered_frames: Dict[int, Set[str]] = {}
        self.acknowledgments: Dict[int, Set[str]] = {}
        self.delivery_times: Dict[int, float] = {}
        self.acknowledged_callbacks: List[Callable[[Frame[T]], None]] = []

        self.on_consumer_register: List[Callable[[str], None]] = []
        self.on_consumer_unregister: List[Callable[[str], None]] = []
        self.on_consumer_pause: List[Callable[[str], None]] = []
        self.on_consumer_resume: List[Callable[[str], None]] = []
        self.on_consumer_circuit_break: List[Callable[[str], None]] = [
            self.circuit_break_hook_warn
        ]

        self.sent_callbacks: List[Callable[[Frame[T]], None]] = []
        self.received_callbacks: List[Callable[[Frame[T]], None]] = []

        self.auto_purge_interval = auto_purge_interval
        self._auto_purge_thread: Optional[threading.Thread] = None
        if self.auto_purge_interval is not None:
            self._auto_purge_thread = threading.Thread(
                target=self._auto_purge_loop, daemon=True
            )
            self._auto_purge_thread.start()

        self.ack_timeout = ack_timeout
        self.max_retries = max_retries
        self.delivery_timeout = delivery_timeout
        self.delivery_timeout_callback: Optional[Callable[[Any, str], None]] = None
        self._ack_monitor_thread = threading.Thread(
            target=self._ack_monitor_loop, daemon=True
        )
        self._ack_monitor_thread.start()

        self.global_rate_limit: Optional[float] = global_rate_limit
        self.last_send_time: float = 0.0

        self.scheduled_tasks: List[threading.Timer] = []

        self.consumer_failures: Dict[str, int] = {}
        self.circuit_breaker_threshold: int = 1000

        self.metrics_callback: Optional[Callable[[Dict[str, Any]], None]] = None
        self.metrics_interval = metrics_interval
        # if self.metrics_interval is not None:
        #     self._metrics_thread = threading.Thread(target=self._metrics_loop, daemon=True)
        #     self._metrics_thread.start()

        self.encrypt_func = encrypt_func
        self.decrypt_func = decrypt_func

        self.send_interceptors: List[Callable[[Frame[T]], Frame[T]]] = []
        self.receive_interceptors: List[Callable[[Frame[T]], Frame[T]]] = []

        self.pre_send_callbacks: List[Callable[[Frame[T]], Frame[T]]] = []
        self.pre_delivery_callbacks: List[Callable[[Frame[T], str], None]] = []

        self.dead_letter_queue: deque[Frame[T]] = deque()

        self.distributed_forwarder = distributed_forwarder
        self.backpressure_callback = backpressure_callback

        self.consumer_info: Dict[str, Dict[str, Any]] = (
            {}
        )  # keys: "topic", "group", "access_token", "weight"
        self.consumer_groups: Dict[str, List[str]] = defaultdict(list)
        self.group_rr_index: Dict[str, int] = {}
        self.consumer_validators: Dict[str, Optional[Callable[[Frame[T]], bool]]] = {}

        self.persist_file = persist_file
        if self.persist_file:
            self.persistence_lock = threading.Lock()
            self.persist_file_handle = open(self.persist_file, "a", buffering=1)
        else:
            self.persist_file_handle = None

        self.config_file = config_file
        if self.config_file:
            self._config_last_modified = os.path.getmtime(self.config_file)
            self._config_thread = threading.Thread(
                target=self._config_reload_loop, daemon=True
            )
            self._config_thread.start()

        self.load_shedding_threshold = load_shedding_threshold

        self.cluster_mode = cluster_mode

        self.pending_requests: Dict[str, threading.Event] = {}
        self.request_responses: Dict[str, Frame[T]] = {}

        self.enrich_plugins: List[Callable[[Frame[T]], Frame[T]]] = []

        self.serialize_plugins: List[Callable[[Frame[T]], Dict[str, Any]]] = []
        self.deserialize_plugins: List[Callable[[Dict[str, Any]], Frame[T]]] = []

        self.deduplication_window = deduplication_window
        self.dedup_cache: Dict[str, float] = {}

        self.listeners: List[FrameListener] = []
        self._listeners_thread = threading.Thread(
            target=self._listeners_loop, daemon=True
        )
        self._listeners_thread.start()

    def circuit_break_hook_warn(self, consumer_id: str) -> None:
        logger.warning(
            f"Consumer {consumer_id} has been paused due to circuit breaking."
        )

    @staticmethod
    def get_consumer_id() -> str:
        return uuid.uuid4().__str__()

    @overload
    def attach(self, listener: "FrameListener") -> None: ...

    @overload
    def attach(
        self, listener: Type["FrameListener"], *args: Any, **kwargs: Any
    ) -> None: ...

    @overload
    def attach(self, listener: Callable[[Self], "FrameListener"]) -> None: ...

    def attach(
        self,
        listener: Union[
            "FrameListener", Type["FrameListener"], Callable[[Self], "FrameListener"]
        ],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        logger.info(f"Attaching Listener to: {self.name}")
        if True:
            if isinstance(listener, FrameListener):
                self.listeners.append(listener)
                logger.info(f"Attached FrameListener instance to: {self.name}")

            elif isinstance(listener, type) and issubclass(listener, FrameListener):
                instance = listener(self, *args, **kwargs)
                self.listeners.append(instance)
                logger.info(
                    f"Attached new FrameListener of type {listener.__name__} to: {self.name}"
                )

            elif callable(listener):
                instance = listener(self)
                self.listeners.append(instance)
                logger.info(
                    f"Attached function callback as FrameListener to: {self.name}"
                )
            else:
                raise TypeError(
                    "attach() accepts a FrameListener instance, a FrameListener subclass, or a callable."
                )

    def _listeners_loop(self) -> None:
        while not self.closed:
            [listener.tick() for listener in self.listeners]
            time.sleep(0.1)

    def _auto_purge_loop(self) -> None:
        """
        Runs in a background thread to periodically purge expired frames from all consumer queues.

        The loop sleeps for self.auto_purge_interval seconds between purges. After each interval,
        it calls the purge_expired_frames() method to remove any frames whose expiration time
        has passed. The loop terminates when the pipeline is closed.
        """
        while not self.closed:
            time.sleep(
                self.auto_purge_interval if self.auto_purge_interval is not None else 1
            )
            self.purge_expired_frames()

    def _apply_global_rate_limit(self) -> None:
        if self.global_rate_limit is not None:
            min_interval = 1.0 / self.global_rate_limit
            now = time.time()
            elapsed = now - self.last_send_time
            if elapsed < min_interval:
                time.sleep(min_interval - elapsed)
            self.last_send_time = time.time()

    def _run_send_interceptors(self, frame_obj: Frame[T]) -> Frame[T]:
        """
        Runs each interceptor function registered in self.send_interceptors on the frame.
        Each interceptor should accept a Frame[T] and return a (possibly modified) Frame[T].
        Any exceptions are caught and logged.
        """
        for interceptor in self.send_interceptors:
            try:
                frame_obj = interceptor(frame_obj)
            except Exception as e:
                logger.error(f"Error in send interceptor: {e}")
        return frame_obj

    def _ack_monitor_loop(self) -> None:
        """
        Monitor delivered frames that have not been acknowledged within ack_timeout.
        If the delivery time exceeds ack_timeout, for each consumer that has not
        acknowledged the frame, increment its failure count and (if delivery_timeout
        is exceeded) trigger a delivery timeout callback. Also, if a consumer's failure
        count exceeds the circuit breaker threshold, the consumer is paused.
        """
        while not self.closed:
            with self.condition:
                now = time.time()
                for frame_id in list(self.delivery_times.keys()):
                    delivery_time = self.delivery_times[frame_id]
                    if (
                        now - delivery_time >= self.ack_timeout
                        if self.ack_timeout is not None
                        else 5
                    ):
                        if frame_id not in self.delivered_frames:
                            continue
                        target_consumers = self.delivered_frames[frame_id]
                        acked = self.acknowledgments.get(frame_id, set())
                        for consumer_id in target_consumers - acked:
                            self.metrics["frames_retried"] += 1
                            logger.info(
                                f"{self.name} Retrying frame {frame_id} for consumer {consumer_id}"
                            )
                            self.consumer_failures[consumer_id] = (
                                self.consumer_failures.get(consumer_id, 0) + 1
                            )
                            if now - delivery_time >= self.delivery_timeout:
                                self.metrics["delivery_timeouts"] += 1
                                if self.delivery_timeout_callback:
                                    try:
                                        self.delivery_timeout_callback(
                                            frame_id, consumer_id
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"Delivery timeout callback error: {e}"
                                        )
                            if (
                                self.consumer_failures[consumer_id]
                                >= self.circuit_breaker_threshold
                            ):
                                self.pause_consumer(consumer_id)
                                for hook in self.on_consumer_circuit_break:
                                    try:
                                        hook(consumer_id)
                                    except Exception as e:
                                        logger.error(
                                            f"Error in circuit breaker hook: {e}"
                                        )
                        del self.delivery_times[frame_id]
            time.sleep(0.5)

    def broadcast(self, frame: Frame[T]) -> None:
        logger.info(f"Broadcasting frame {frame.id} in cluster mode (stub).")

    def _config_reload_loop(self) -> None:
        while not self.closed:
            try:
                current = os.path.getmtime(
                    self.config_file if self.config_file else "./config"
                )
                if current != self._config_last_modified:
                    self._config_last_modified = current
                    self._reload_config()
            except Exception as e:
                logger.error(f"Config reload error: {e}")
            time.sleep(2)

    def _reload_config(self) -> None:
        try:
            with open(self.config_file if self.config_file else "./config", "r") as f:
                config = json.load(f)
            for cid, settings in config.get("consumers", {}).items():
                if cid in self.consumers:
                    self.update_consumer_config(
                        cid,
                        max_queue_size=settings.get("max_queue_size"),
                        overflow_policy=settings.get("overflow_policy"),
                        rate_limit=settings.get("rate_limit"),
                    )
                    logger.info(f"Reloaded config for consumer {cid}.")
        except Exception as e:
            logger.error(f"Error reloading config: {e}")

    def send_request(
        self,
        frame: T,
        metadata: Optional[Dict[str, Any]] = None,
        timeout: Optional[float] = 5.0,
        **kwargs,
    ) -> Optional[Frame[T]]:
        correlation_id = str(uuid.uuid4())
        kwargs["correlation_id"] = correlation_id
        event = threading.Event()
        self.pending_requests[correlation_id] = event
        self.send(frame, metadata=metadata, **kwargs)
        if event.wait(timeout):
            response = self.request_responses.pop(correlation_id, None)
            self.pending_requests.pop(correlation_id, None)
            return response
        else:
            self.pending_requests.pop(correlation_id, None)
            return None

    def process_response(self, frame: Frame[T]) -> None:
        if frame.correlation_id and frame.correlation_id in self.pending_requests:
            self.request_responses[frame.correlation_id] = frame
            self.pending_requests[frame.correlation_id].set()

    def _run_enrich_plugins(self, frame_obj: Frame[T]) -> Frame[T]:
        for plugin in self.enrich_plugins:
            try:
                frame_obj = plugin(frame_obj)
            except Exception as e:
                logger.error(f"Error in enrichment plugin: {e}")
        return frame_obj

    def _run_serialize_plugins(self, frame_obj: Frame[T]) -> Dict[str, Any]:
        record = {
            "id": frame_obj.id,
            "timestamp": frame_obj.timestamp,
            "data": frame_obj.data,
            "metadata": frame_obj.metadata,
            "sender_id": frame_obj.sender_id,
            "priority": frame_obj.priority,
            "expire_at": frame_obj.expire_at,
            "available_at": frame_obj.available_at,
            "correlation_id": frame_obj.correlation_id,
            "topic": frame_obj.topic,
            "annotations": frame_obj.annotations,
        }
        for plugin in self.serialize_plugins:
            try:
                record = plugin(frame_obj)
            except Exception as e:
                logger.error(f"Error in serialize plugin: {e}")
        return record

    def _run_deserialize_plugins(self, record: Dict[str, Any]) -> Frame[T]:
        frame_obj = Frame(
            id=record["id"],
            timestamp=record["timestamp"],
            data=record["data"],
            metadata=record.get("metadata"),
            sender_id=record.get("sender_id"),
            priority=record.get("priority", 0),
            expire_at=record.get("expire_at"),
            available_at=record.get("available_at"),
            correlation_id=record.get("correlation_id"),
            topic=record.get("topic"),
            annotations=record.get("annotations", {}),
        )
        for plugin in self.deserialize_plugins:
            try:
                frame_obj = plugin(record)
            except Exception as e:
                logger.error(f"Error in deserialize plugin: {e}")
        return frame_obj

    def _persist_frame(self, frame_obj: Frame[T]) -> None:
        if self.persist_file_handle:
            try:
                with self.persistence_lock:
                    record = self._run_serialize_plugins(frame_obj)
                    self.persist_file_handle.write(json.dumps(record) + "\n")
            except Exception as e:
                logger.error(f"Persistence error: {e}")

    def _should_shed(self, frame_obj: Frame[T]) -> bool:
        if self.load_shedding_threshold is not None:
            if (
                self.queue.qsize() > self.load_shedding_threshold
                and frame_obj.priority > 5
            ):
                return True
        return False

    def _check_dedup(self, correlation_id: str) -> bool:
        now = time.time()
        if correlation_id in self.dedup_cache:
            if now - self.dedup_cache[correlation_id] < self.deduplication_window:
                return True
        self.dedup_cache[correlation_id] = now
        keys_to_delete = [
            cid
            for cid, tstamp in self.dedup_cache.items()
            if now - tstamp >= self.deduplication_window
        ]
        for cid in keys_to_delete:
            del self.dedup_cache[cid]
        return False

    def _run_pre_send_hooks(self, frame_obj: Frame[T]) -> Frame[T]:
        for hook in self.pre_send_callbacks:
            try:
                frame_obj = hook(frame_obj)
            except Exception as e:
                logger.error(f"Error in pre-send hook: {e}")
        return frame_obj

    def send(
        self,
        frame: T,
        metadata: Optional[Dict[str, Any]] = None,
        required_by: Optional[List[str]] = None,
        timeout: Optional[float] = None,
        priority: Optional[int] = None,
        ttl: Optional[float] = None,
        delay: Optional[float] = None,
        correlation_id: Optional[str] = None,
        topic: Optional[str] = None,
        sender_id: Optional[str] = None,
    ) -> None:
        with self.condition:
            if self.closed:
                raise RuntimeError("Pipeline is closed.")
            self._apply_global_rate_limit()
            self.frame_counter += 1
            now = time.time()
            avail_at = (
                now + delay
                if (delay is not None and self.enable_delayed_delivery)
                else now
            )
            if correlation_id is None:
                correlation_id = str(uuid.uuid4())
            if self._check_dedup(correlation_id):
                logger.info(
                    f"Duplicate frame with correlation_id {correlation_id} detected; dropping."
                )
                return
            frame_obj = Frame(
                data=frame,
                metadata=metadata,
                timestamp=now,
                sender_id=sender_id,
                id=self.frame_counter,
                priority=priority if priority is not None else 0,
                expire_at=(now + ttl) if ttl is not None else None,
                available_at=avail_at,
                correlation_id=correlation_id,
                topic=topic,
            )
            self.metrics["frames_sent"] += 1
            frame_obj = self._run_pre_send_hooks(frame_obj)
            frame_obj = self._run_send_interceptors(frame_obj)
            frame_obj = self._run_enrich_plugins(frame_obj)
            if self.encrypt_func is not None:
                try:
                    frame_obj.data = self.encrypt_func(frame_obj.data)
                except Exception as e:
                    logger.error(f"Encryption error: {e}")
            self._persist_frame(frame_obj)
        if self._should_shed(frame_obj):
            with self.lock:
                self.metrics["frames_dropped"] += 1
            logger.warning(f"Frame {frame_obj.id} shed due to overload.")
            return
        try:
            self.queue.put(frame_obj, block=True, timeout=timeout)
        except queue.Full:
            with self.lock:
                self.metrics["frames_dropped"] += 1
            logger.warning("Main queue is full. Frame discarded.")
            raise
        with self.condition:
            target_consumers: List[str] = []
            if required_by is not None:
                target_consumers = required_by
            else:
                if frame_obj.topic is not None:
                    non_group = []
                    groups_to_deliver = set()
                    for cid, info in self.consumer_info.items():
                        if info.get("topic") == frame_obj.topic:
                            grp = info.get("group")
                            if grp:
                                groups_to_deliver.add(grp)
                            else:
                                non_group.append(cid)
                    for grp in groups_to_deliver:
                        chosen = self._weighted_round_robin(grp)
                        target_consumers.append(chosen)
                    target_consumers.extend(non_group)
                else:
                    target_consumers = list(self.consumers.keys())
            frame_obj.delivered_to = target_consumers.copy()
            self.delivered_frames[frame_obj.id] = set(target_consumers)
            self.acknowledgments[frame_obj.id] = set()
            self.delivery_times[frame_obj.id] = time.time()
            for consumer_id in target_consumers:
                info = self.consumer_info.get(consumer_id, {})
                required_token = info.get("access_token")
                if required_token is not None:
                    if not (
                        metadata and metadata.get("access_token") == required_token
                    ):
                        logger.info(
                            f"Frame {frame_obj.id} not delivered to consumer '{consumer_id}' due to access token mismatch."
                        )
                        continue
                validator = self.consumer_validators.get(consumer_id)
                if validator and not validator(frame_obj):
                    logger.info(
                        f"Frame {frame_obj.id} rejected by validator for consumer '{consumer_id}'."
                    )
                    continue
                consumer_queue = self.consumers[consumer_id]
                max_q = self.consumer_maxsize.get(consumer_id)
                overflow = self.consumer_overflow_policy.get(consumer_id, "drop")
                now = time.time()
                last_time = self.consumer_last_receive.get(consumer_id, 0)
                rate_limit = self.consumer_rate_limits.get(consumer_id, float("inf"))
                min_interval = 1.0 / rate_limit if rate_limit != float("inf") else 0.0
                if now - last_time < min_interval:
                    wait_time = min_interval - (now - last_time)
                    self.condition.wait(timeout=wait_time)
                if max_q is not None and len(consumer_queue) >= max_q:
                    if self.backpressure_callback is not None:
                        try:
                            self.backpressure_callback(consumer_id, len(consumer_queue))
                        except Exception as e:
                            logger.error(f"Backpressure callback error: {e}")
                    if overflow == "drop":
                        self.metrics["frames_dropped"] += 1
                        self.consumer_metrics[consumer_id]["frames_dropped"] += 1
                        logger.warning(
                            f"Frame dropped for consumer '{consumer_id}' due to full queue."
                        )
                        continue
                    elif overflow == "error":
                        raise RuntimeError(f"Consumer '{consumer_id}' queue is full.")
                    elif overflow == "block":
                        remaining = timeout
                        self.condition.wait(timeout=remaining)
                if self.sorted_queues:
                    self._insort_consumer_queue(consumer_queue, frame_obj)
                else:
                    consumer_queue.append(frame_obj)
            for callback in self.sent_callbacks:
                try:
                    callback(frame_obj)
                except Exception as e:
                    logger.error(f"Sent callback error: {e}")
            self.condition.notify_all()
            if self.distributed_forwarder is not None:
                try:
                    self.distributed_forwarder(frame_obj)
                except Exception as e:
                    logger.error(f"Distributed forwarder error: {e}")
            if self.cluster_mode:
                self.broadcast(frame_obj)

    def send_nowait(self, *args, **kwargs) -> None:
        self.send(*args, **kwargs)

    def _consumer_queue_pop(self, consumer_id: str) -> Optional[Frame[T]]:
        if self.sorted_queues:
            qlist: List[Frame[T]] = self.consumers[consumer_id]
            if qlist:
                if qlist[0].available_at > time.time():
                    return None
                return qlist.pop(0)
            return None
        else:
            dq: deque = self.consumers[consumer_id]
            if dq:
                return dq.popleft()
            return None

    def _run_receive_interceptors(self, frame_obj: Frame[T]) -> Frame[T]:
        """
        Runs each interceptor function registered in self.receive_interceptors on the frame.
        Each interceptor should accept a Frame[T] and return a (possibly modified) Frame[T].
        Any exceptions are caught and logged.
        """
        for interceptor in self.receive_interceptors:
            try:
                frame_obj = interceptor(frame_obj)
            except Exception as e:
                logger.error(f"Error in receive interceptor: {e}")
        return frame_obj

    def _insort_consumer_queue(
        self, queue_list: List[Frame[T]], frame_obj: Frame[T]
    ) -> None:
        """
        Inserts 'frame_obj' into 'queue_list', maintaining the sorted order.
        The frames are sorted by a tuple key: (available_at, priority, id).

        Parameters:
            queue_list (List[Frame[T]]): The list of frames (assumed to be already sorted).
            frame_obj (Frame[T]): The frame to insert.
        """
        key = (frame_obj.available_at, frame_obj.priority, frame_obj.id)
        lo = 0
        hi = len(queue_list)
        while lo < hi:
            mid = (lo + hi) // 2
            mid_frame = queue_list[mid]
            mid_key = (mid_frame.available_at, mid_frame.priority, mid_frame.id)
            if key < mid_key:
                hi = mid
            else:
                lo = mid + 1
        queue_list.insert(lo, frame_obj)

    def receive(
        self, consumer_id: str, block: bool = True, timeout: Optional[float] = None
    ) -> Optional[Frame[T]]:
        with self.condition:
            if consumer_id not in self.consumers:
                self.register_consumer(consumer_id)
            consumer_queue = self.consumers[consumer_id]
            start_time = time.monotonic()
            while True:
                if self.consumer_status.get(consumer_id, False):
                    remaining = (
                        None
                        if timeout is None
                        else timeout - (time.monotonic() - start_time)
                    )
                    if timeout is not None and remaining is not None and remaining <= 0:
                        return None
                    self.condition.wait(timeout=remaining)
                    continue

                now = time.time()
                last_time = self.consumer_last_receive.get(consumer_id, 0)
                rate_limit = self.consumer_rate_limits.get(consumer_id, float("inf"))
                min_interval = 1.0 / rate_limit if rate_limit != float("inf") else 0.0
                if now - last_time < min_interval:
                    wait_time = min_interval - (now - last_time)
                    self.condition.wait(timeout=wait_time)

                frame_obj = self._consumer_queue_pop(consumer_id)
                if frame_obj is not None:
                    if (
                        frame_obj.expire_at is not None
                        and time.time() > frame_obj.expire_at
                    ):
                        self.metrics["frames_expired"] += 1
                        self.consumer_metrics[consumer_id]["frames_expired"] += 1
                        logger.debug(
                            f"Expired frame dropped for consumer '{consumer_id}': {frame_obj}"
                        )
                        continue

                    if frame_obj.available_at and frame_obj.available_at > time.time():
                        wait_time = frame_obj.available_at - time.time()
                        if not block:
                            if self.sorted_queues:
                                self._insort_consumer_queue(consumer_queue, frame_obj)
                            else:
                                consumer_queue.appendleft(frame_obj)
                            return None
                        else:
                            self.condition.wait(timeout=wait_time)
                            continue

                    filter_fn = self.consumer_filters.get(consumer_id)
                    if filter_fn is not None:
                        try:
                            if not filter_fn(frame_obj):
                                logger.debug(
                                    f"Frame {frame_obj.id} filtered out for consumer '{consumer_id}'."
                                )
                                continue
                        except Exception as e:
                            logger.error(
                                f"Error applying filter for consumer '{consumer_id}': {e}"
                            )
                            continue

                    self.metrics["frames_received"] += 1
                    self.consumer_metrics[consumer_id]["frames_received"] += 1
                    delay_time = max(0.0, time.time() - frame_obj.available_at)
                    self.consumer_metrics[consumer_id][
                        "total_frame_delay"
                    ] += delay_time
                    self.consumer_metrics[consumer_id]["frame_delay_count"] += 1
                    self.consumer_last_receive[consumer_id] = time.time()

                    for hook in self.pre_delivery_callbacks:
                        try:
                            hook(frame_obj, consumer_id)
                        except Exception as e:
                            logger.error(f"Pre-delivery hook error: {e}")

                    frame_obj = self._run_receive_interceptors(frame_obj)

                    if self.decrypt_func is not None:
                        try:
                            frame_obj.data = self.decrypt_func(frame_obj.data)
                        except Exception as e:
                            logger.error(f"Decryption error: {e}")

                    if frame_obj.is_response:
                        self.process_response(frame_obj)

                    for callback in self.received_callbacks:
                        try:
                            callback(frame_obj)
                        except Exception as e:
                            logger.error(f"Received callback error: {e}")

                    logger.debug(f"Frame received by {consumer_id}: {frame_obj}")

                    # Acknowledge the frame
                    self.acknowledge(consumer_id, frame_obj.id)
                    return frame_obj

                if not block:
                    return None

                remaining = (
                    None
                    if timeout is None
                    else timeout - (time.monotonic() - start_time)
                )
                if timeout is not None and remaining is not None and remaining <= 0:
                    return None

                self.condition.wait(timeout=remaining)
                if self.closed and not consumer_queue:
                    return None

    def batch_receive(self, consumer_id: str, max_frames: int) -> List[Frame[T]]:
        frames = []
        for _ in range(max_frames):
            f = self.receive(consumer_id, block=False)
            if f is None:
                break
            frames.append(f)
        return frames

    def iterate_frames(
        self, consumer_id: str, timeout: Optional[float] = None
    ) -> Iterator[Frame[T]]:
        while True:
            f = self.receive(consumer_id, block=True, timeout=timeout)
            if f is None:
                break
            yield f

    def purge_expired_frames(self) -> None:
        now = time.time()
        with self.condition:
            for cid, q in self.consumers.items():
                if self.sorted_queues:
                    new_q = [f for f in q if f.expire_at is None or now <= f.expire_at]
                    dropped = len(q) - len(new_q)
                    if dropped > 0:
                        self.metrics["frames_expired"] += dropped
                        self.consumer_metrics[cid]["frames_expired"] += dropped
                    self.consumers[cid] = new_q
                else:
                    init = len(q)
                    remaining = deque()
                    while q:
                        f = q.popleft()
                        if f.expire_at is None or now <= f.expire_at:
                            remaining.append(f)
                        else:
                            self.metrics["frames_expired"] += 1
                            self.consumer_metrics[cid]["frames_expired"] += 1
                    self.consumers[cid] = remaining
            self.condition.notify_all()

    def acknowledge(self, consumer_id: str, frame_id: int) -> None:
        if True:
            if frame_id not in self.acknowledgments:
                logger.warning(f"Frame {frame_id} not found for acknowledgment.")
                return
            self.acknowledgments[frame_id].add(consumer_id)
            delivered = self.delivered_frames.get(frame_id, set())
            if self.acknowledgments[frame_id] == delivered:
                for callback in self.acknowledged_callbacks:
                    try:
                        dummy = Frame(
                            data=None,
                            metadata=None,
                            timestamp=0,
                            sender_id=None,
                            id=frame_id,
                            priority=0,
                            expire_at=None,
                            available_at=0,
                        )
                        callback(dummy)
                    except Exception as e:
                        logger.error(f"Acknowledged callback error: {e}")
                del self.acknowledgments[frame_id]
                if frame_id in self.delivered_frames:
                    del self.delivered_frames[frame_id]

    def add_to_dead_letter(self, frame_obj: Frame[T]) -> None:
        with self.lock:
            self.dead_letter_queue.append(frame_obj)
            logger.info(f"Frame {frame_obj.id} moved to dead-letter queue.")

    def get_dead_letter_frames(self) -> List[Frame[T]]:
        with self.lock:
            return list(self.dead_letter_queue)

    def requeue_dead_letter_frames(self) -> None:
        with self.condition:
            while self.dead_letter_queue:
                f = self.dead_letter_queue.popleft()
                self.queue.put(f)
            self.condition.notify_all()

    def transactional_send(
        self, frames: List[T], metadata: Optional[Dict[str, Any]] = None, **kwargs
    ) -> None:
        successful = []
        try:
            for f in frames:
                self.send(f, metadata=metadata, **kwargs)
                successful.append(f)
        except Exception as e:
            logger.error(f"Transactional send failed: {e}. Rolling back.")
            for f in successful:
                dummy = Frame(
                    data=f,
                    metadata=metadata,
                    timestamp=time.time(),
                    sender_id=self.sender_id,
                    id=self.frame_counter,
                    priority=0,
                    expire_at=None,
                    available_at=time.time(),
                    correlation_id=str(uuid.uuid4()),
                )
                self.add_to_dead_letter(dummy)
            raise

    async def async_send(self, *args, **kwargs) -> None:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, self.send, *args, **kwargs)

    async def async_receive(
        self, consumer_id: str, block: bool = True, timeout: Optional[float] = None
    ) -> Optional[Frame[T]]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self.receive, consumer_id, block, timeout
        )

    def start_metrics_server(self, port: int = 8000) -> None:
        from http.server import BaseHTTPRequestHandler, HTTPServer

        pipeline = self

        class MetricsHandler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path == "/metrics":
                    metrics = pipeline.get_metrics()
                    lines = []
                    for k, v in metrics["global"].items():
                        lines.append(f"pipeline_{k} {v}")
                    for cid, m in metrics["consumers"].items():
                        for k, v in m.items():
                            lines.append(
                                f'pipeline_consumer{{id="{cid}",metric="{k}"}} {v}'
                            )
                    output = "\n".join(lines)
                    self.send_response(200)
                    self.send_header("Content-type", "text/plain; version=0.0.4")
                    self.end_headers()
                    self.wfile.write(output.encode("utf-8"))
                else:
                    self.send_error(404)

        server = HTTPServer(("", port), MetricsHandler)
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
        logger.info(f"Metrics server started on port {port}.")

    def _weighted_round_robin(self, group: str) -> str:
        members = self.consumer_groups.get(group, [])
        if not members:
            raise ValueError(f"No consumers in group {group}")
        total_weight = 0
        weighted_list = []
        for cid in members:
            weight = self.consumer_info.get(cid, {}).get("weight", 1)
            total_weight += weight
            weighted_list.append((cid, weight))
        index = self.group_rr_index.get(group, 0)
        counter = index % total_weight
        for cid, weight in weighted_list:
            if counter < weight:
                self.group_rr_index[group] = index + 1
                return cid
            counter -= weight
        self.group_rr_index[group] = index + 1
        return members[0]

    def register_consumer(
        self,
        consumer_id: str,
        filter_fn: Optional[Callable[[Frame[T]], bool]] = None,
        max_queue_size: Optional[int] = None,
        overflow_policy: str = "drop",
        rate_limit: Optional[float] = None,
        topic: str = "default",
        group: Optional[str] = None,
        validate_func: Optional[Callable[[Frame[T]], bool]] = None,
        access_token: Optional[str] = None,
        weight: int = 1,
    ) -> None:
        with self.lock:
            if consumer_id in self.consumers:
                raise ValueError(f"Consumer '{consumer_id}' is already registered.")
            if self.sorted_queues:
                self.consumers[consumer_id] = []
            else:
                self.consumers[consumer_id] = deque()
            self.consumer_filters[consumer_id] = filter_fn
            self.consumer_status[consumer_id] = False
            self.consumer_maxsize[consumer_id] = max_queue_size
            if overflow_policy not in ("drop", "error", "block"):
                raise ValueError("overflow_policy must be 'drop', 'error', or 'block'")
            self.consumer_overflow_policy[consumer_id] = overflow_policy
            self.consumer_rate_limits[consumer_id] = (
                rate_limit if rate_limit is not None else float("inf")
            )
            self.consumer_last_receive[consumer_id] = 0.0
            self.consumer_metrics[consumer_id] = {
                "frames_received": 0,
                "frames_expired": 0,
                "frames_dropped": 0,
                "total_frame_delay": 0.0,
                "frame_delay_count": 0,
            }
            self.consumer_failures[consumer_id] = 0
            self.consumer_info[consumer_id] = {
                "topic": topic,
                "group": group,
                "access_token": access_token,
                "weight": weight,
            }
            self.consumer_validators[consumer_id] = validate_func
            if group is not None:
                self.consumer_groups[group].append(consumer_id)
                if group not in self.group_rr_index:
                    self.group_rr_index[group] = 0
            logger.info(
                f"Consumer '{consumer_id}' registered on topic '{topic}' with group '{group}', weight {weight}."
            )
            for hook in self.on_consumer_register:
                try:
                    hook(consumer_id)
                except Exception as e:
                    logger.error(f"Error in on_consumer_register hook: {e}")

    def unregister_consumer(self, consumer_id: str) -> None:
        with self.lock:
            if consumer_id not in self.consumers:
                raise ValueError(f"Consumer '{consumer_id}' is not registered.")
            info = self.consumer_info.get(consumer_id, {})
            group = info.get("group")
            if group and consumer_id in self.consumer_groups.get(group, []):
                self.consumer_groups[group].remove(consumer_id)
            del self.consumer_info[consumer_id]
            self.consumer_validators.pop(consumer_id, None)
            del self.consumers[consumer_id]
            self.consumer_filters.pop(consumer_id, None)
            self.consumer_status.pop(consumer_id, None)
            self.consumer_maxsize.pop(consumer_id, None)
            self.consumer_overflow_policy.pop(consumer_id, None)
            self.consumer_rate_limits.pop(consumer_id, None)
            self.consumer_last_receive.pop(consumer_id, None)
            self.consumer_metrics.pop(consumer_id, None)
            self.consumer_failures.pop(consumer_id, None)
            logger.info(f"Consumer '{consumer_id}' unregistered.")
            for hook in self.on_consumer_unregister:
                try:
                    hook(consumer_id)
                except Exception as e:
                    logger.error(f"Error in on_consumer_unregister hook: {e}")

    def pause_consumer(self, consumer_id: str) -> None:
        # with self.lock:
        if consumer_id not in self.consumer_status:
            raise ValueError(f"Consumer '{consumer_id}' is not registered.")
        self.consumer_status[consumer_id] = True
        logger.info(f"Consumer '{consumer_id}' paused.")
        for hook in self.on_consumer_pause:
            try:
                hook(consumer_id)
            except Exception as e:
                logger.error(f"Error in on_consumer_pause hook: {e}")

    def resume_consumer(self, consumer_id: str) -> None:
        with self.lock:
            if consumer_id not in self.consumer_status:
                raise ValueError(f"Consumer '{consumer_id}' is not registered.")
            self.consumer_status[consumer_id] = False
            self.condition.notify_all()
            logger.info(f"Consumer '{consumer_id}' resumed.")
            for hook in self.on_consumer_resume:
                try:
                    hook(consumer_id)
                except Exception as e:
                    logger.error(f"Error in on_consumer_resume hook: {e}")

    def update_consumer_config(
        self,
        consumer_id: str,
        max_queue_size: Optional[int] = None,
        overflow_policy: Optional[str] = None,
        rate_limit: Optional[float] = None,
    ) -> None:
        with self.lock:
            if consumer_id not in self.consumers:
                raise ValueError(f"Consumer '{consumer_id}' not registered.")
            if max_queue_size is not None:
                self.consumer_maxsize[consumer_id] = max_queue_size
            if overflow_policy is not None:
                if overflow_policy not in ("drop", "error", "block"):
                    raise ValueError(
                        "overflow_policy must be 'drop', 'error', or 'block'"
                    )
                self.consumer_overflow_policy[consumer_id] = overflow_policy
            if rate_limit is not None:
                self.consumer_rate_limits[consumer_id] = rate_limit

    def get_consumer_info(self) -> Dict[str, Dict[str, Any]]:
        with self.lock:
            return self.consumer_info.copy()

    def get_metrics(self) -> Dict[str, Any]:
        """
        Returns a dictionary containing a snapshot of global and per‑consumer metrics.
        The returned dictionary includes:
        - "global": a copy of the global metrics dictionary.
        - "consumers": a dictionary mapping each consumer ID to its metrics.
        - "consumer_average_delay": a dictionary mapping each consumer ID to its
             average frame delivery delay.
        """
        with self.lock:
            consumer_avg_delay = {}
            for cid, m in self.consumer_metrics.items():
                count = m.get("frame_delay_count", 0)
                total = m.get("total_frame_delay", 0.0)
                avg = total / count if count > 0 else 0.0
                consumer_avg_delay[cid] = avg

            return {
                "global": self.metrics.copy(),
                "consumers": {
                    cid: m.copy() for cid, m in self.consumer_metrics.items()
                },
                "consumer_average_delay": consumer_avg_delay,
            }

    def health_check(self) -> Dict[str, Any]:
        with self.lock:
            queue_size = self.queue.qsize()
            consumer_count = len(self.consumers)
            dead_letter_count = len(self.dead_letter_queue)
            consumer_info = self.consumer_info.copy()
            consumer_groups = dict(self.consumer_groups)
        metrics = self.get_metrics()
        return {
            "queue_size": queue_size,
            "consumer_count": consumer_count,
            "dead_letter_count": dead_letter_count,
            "metrics": metrics,
            "consumer_info": consumer_info,
            "consumer_groups": consumer_groups,
        }

    def replay_frames(self) -> List[Dict[str, Any]]:
        if self.persist_file:
            try:
                with self.persistence_lock, open(self.persist_file, "r") as f:
                    return [json.loads(line) for line in f if line.strip()]
            except Exception as e:
                logger.error(f"Replay error: {e}")
                return []
        return []

    def clear(self) -> None:
        with self.condition:
            with self.queue.mutex:
                self.queue.queue.clear()
            for cid in self.consumers:
                self.consumers[cid].clear()
            logger.info("Pipeline cleared.")

    def qsize(self) -> int:
        with self.lock:
            return self.queue.qsize()

    def get_consumer_queue_size(self, consumer_id: str) -> int:
        with self.lock:
            return len(self.consumers.get(consumer_id, []))

    def close(self) -> None:
        with self.condition:
            self.closed = True
            self.condition.notify_all()
        self.clear()
        logger.info("Pipeline closed.")
        if self._auto_purge_thread:
            self._auto_purge_thread.join(timeout=0.1)
        if self._ack_monitor_thread:
            self._ack_monitor_thread.join(timeout=0.1)
        if self.persist_file_handle:
            self.persist_file_handle.close()

    def is_closed(self) -> bool:
        with self.lock:
            return self.closed

    def schedule_frame(
        self,
        interval: float,
        frame: T,
        metadata: Optional[Dict[str, Any]] = None,
        required_by: Optional[List[str]] = None,
        priority: Optional[int] = None,
        ttl: Optional[float] = None,
        delay: Optional[float] = None,
        correlation_id: Optional[str] = None,
        topic: Optional[str] = None,
    ) -> Callable[[], None]:
        def _send_and_reschedule():
            try:
                self.send(
                    frame,
                    metadata=metadata,
                    required_by=required_by,
                    priority=priority,
                    ttl=ttl,
                    delay=delay,
                    correlation_id=correlation_id,
                    topic=topic,
                )
            except Exception as e:
                logger.error(f"Error sending scheduled frame: {e}")
            if not self.closed:
                t = threading.Timer(interval, _send_and_reschedule)
                with self.lock:
                    self.scheduled_tasks.append(t)
                t.start()

        t = threading.Timer(interval, _send_and_reschedule)
        with self.lock:
            self.scheduled_tasks.append(t)
        t.start()

        def cancel():
            t.cancel()

        return cancel


import pytest


def test_basic_send_receive():
    pipeline = FramePipeline[int]()
    pipeline.register_consumer("consumer1")
    pipeline.send(42)
    frame = pipeline.receive("consumer1", block=False)
    assert frame is not None and frame.data == 42
    pipeline.close()


def test_consumer_filtering():
    pipeline = FramePipeline[int]()
    pipeline.register_consumer("even_consumer", filter_fn=lambda f: f.data % 2 == 0)
    pipeline.register_consumer("all_consumer")
    pipeline.send(3)
    pipeline.send(4)
    frame_even = pipeline.receive("even_consumer", block=False)
    print(frame_even)
    assert frame_even is not None and frame_even.data == 4
    frame_all1 = pipeline.receive("all_consumer", block=False)
    frame_all2 = pipeline.receive("all_consumer", block=False)
    received_data = sorted([frame_all1.data, frame_all2.data])
    assert received_data == [3, 4]
    pipeline.close()


def test_consumer_groups_and_topics():
    pipeline = FramePipeline[int]()
    pipeline.register_consumer(
        "news_consumer_1", topic="news", group="group1", weight=3
    )
    pipeline.register_consumer(
        "news_consumer_2", topic="news", group="group1", weight=1
    )
    pipeline.register_consumer("sports_consumer", topic="sports")
    pipeline.send(100, topic="news")
    received = pipeline.batch_receive("news_consumer_1", 1) + pipeline.batch_receive(
        "news_consumer_2", 1
    )
    assert len(received) == 1 and received[0].data == 100
    pipeline.send(200, topic="sports")
    frame_sports = pipeline.receive("sports_consumer", block=False)
    assert frame_sports is not None and frame_sports.data == 200
    pipeline.close()


def test_persistence_and_replay(tmp_path):
    persist_file = str(tmp_path / "pipeline.log")
    pipeline = FramePipeline[str](persist_file=persist_file)
    pipeline.register_consumer("consumer1")
    pipeline.send("persisted frame")
    time.sleep(0.1)
    replayed = pipeline.replay_frames()
    assert any("persisted frame" in record["data"] for record in replayed)
    pipeline.close()


def test_encryption_decryption():
    encrypt = lambda d: d[::-1] if isinstance(d, str) else d
    decrypt = lambda d: d[::-1] if isinstance(d, str) else d
    pipeline = FramePipeline[str](encrypt_func=encrypt, decrypt_func=decrypt)
    pipeline.register_consumer("consumer1")
    pipeline.send("hello")
    frame = pipeline.receive("consumer1", block=False)
    assert frame is not None and frame.data == "hello"
    pipeline.close()


def test_interceptors():
    def send_interceptor(frame: Frame[str]) -> Frame[str]:
        if isinstance(frame.data, str):
            frame.data += "-intercepted"
        return frame

    pipeline = FramePipeline[str]()
    pipeline.send_interceptors.append(send_interceptor)
    pipeline.register_consumer("consumer1")
    pipeline.send("data")
    frame = pipeline.receive("consumer1", block=False)
    assert frame is not None and frame.data == "data-intercepted"
    pipeline.close()


def test_correlation_id():
    pipeline = FramePipeline[int]()
    pipeline.register_consumer("consumer1")
    pipeline.send(55)
    frame = pipeline.receive("consumer1", block=False)
    assert frame is not None and frame.correlation_id is not None
    pipeline.close()


def test_distributed_forwarder():
    forwarded = []

    def forwarder(frame: Frame[int]):
        forwarded.append(frame.data)

    pipeline = FramePipeline[int](distributed_forwarder=forwarder)
    pipeline.register_consumer("consumer1")
    pipeline.send(777)
    time.sleep(0.1)
    assert 777 in forwarded
    pipeline.close()


def test_transactional_send():
    pipeline = FramePipeline[int]()
    pipeline.register_consumer("consumer1")
    try:
        pipeline.transactional_send([100, 200, 300])
    except Exception:
        pass
    frames = pipeline.batch_receive("consumer1", 3)
    assert len(frames) == 3
    pipeline.close()


@pytest.mark.asyncio
async def test_async_send_receive():
    pipeline = FramePipeline[int]()
    pipeline.register_consumer("async_consumer")
    await pipeline.async_send(123)
    frame = await pipeline.async_receive("async_consumer", block=True, timeout=1)
    assert frame is not None and frame.data == 123
    pipeline.close()


def test_iterate_frames():
    pipeline = FramePipeline[int]()
    pipeline.register_consumer("consumer_iter")
    for i in range(5):
        pipeline.send(i)
    frames = list(pipeline.iterate_frames("consumer_iter", timeout=0.1))
    assert len(frames) == 5
    assert [f.data for f in frames] == list(range(5))
    pipeline.close()


def test_schedule_frame():
    pipeline = FramePipeline[int]()
    pipeline.register_consumer("scheduler_consumer")
    cancel = pipeline.schedule_frame(0.5, 999)
    time.sleep(1.2)
    frames = pipeline.batch_receive("scheduler_consumer", 10)
    assert len(frames) >= 2
    cancel()
    pipeline.close()


def test_dead_letter_queue():
    pipeline = FramePipeline[int]()
    try:
        pipeline.transactional_send([111, 222])
    except Exception:
        pass
    dummy = Frame(
        available_at=time.time(),
        priority=0,
        id=999,
        data=999,
        correlation_id=str(uuid.uuid4()),
    )
    pipeline.add_to_dead_letter(dummy)
    dl = pipeline.get_dead_letter_frames()
    assert any(f.id == 999 for f in dl)
    pipeline.close()


def test_health_check():
    pipeline = FramePipeline[int]()
    pipeline.register_consumer("consumer1")
    pipeline.send(42)
    health = pipeline.health_check()
    assert "queue_size" in health and health["consumer_count"] >= 1
    pipeline.close()


def test_deduplication():
    pipeline = FramePipeline[int](deduplication_window=2.0)
    pipeline.register_consumer("consumer1")
    cid = str(uuid.uuid4())
    pipeline.send(123, correlation_id=cid)
    # Second send with same correlation_id within window should be dropped.
    pipeline.send(456, correlation_id=cid)
    frame = pipeline.receive("consumer1", block=False)
    assert frame is not None and frame.data == 123
    pipeline.close()


def test_pre_send_and_pre_delivery_hooks():
    def pre_send(frame: Frame[str]) -> Frame[str]:
        frame.data = "pre_send_" + frame.data
        return frame

    def pre_delivery(frame: Frame[str], cid: str):
        frame.data = frame.data + "_pre_delivery"

    pipeline = FramePipeline[str]()
    pipeline.pre_send_callbacks.append(pre_send)
    pipeline.pre_delivery_callbacks.append(pre_delivery)
    pipeline.register_consumer("consumer1")
    pipeline.send("data")
    frame = pipeline.receive("consumer1", block=False)
    assert frame is not None and frame.data == "pre_send_data_pre_delivery"
    pipeline.close()


class FrameListener:
    def __init__(
        self,
        pipeline: FramePipeline[Any],
        on_tick: Optional[Callable[[Frame[Any]], None]] = None,
        *args,
        **kwargs,
    ) -> None:
        self.pipeline = pipeline
        self.on_tick = on_tick

        self.consumer_id = FramePipeline.get_consumer_id()

        self.pipeline.register_consumer(self.consumer_id)

    def tick(self):
        if self.pipeline.closed:
            logger.error("Pipeline already closed")
            return
        frame = self.pipeline.receive(self.consumer_id, block=True, timeout=1)
        if frame is not None and self.on_tick is not None:
            self.on_tick(frame)
        else:
            time.sleep(0.1)


def frame_printer(pipeline: FramePipeline[Any]) -> FrameListener:
    """
    Continuously receives frames from the pipeline using the given consumer ID.
    When a frame is received, it is printed to standard output.
    The thread exits when the pipeline is closed.
    """

    return FrameListener(pipeline, lambda frame: print("Frame Listener:", frame))


class PipelineSupplier(Generic[T]):
    def __init__(
        self,
        event_pipeline: FramePipeline[Event],
        state_pipeline: FramePipeline[StateData],
        initial: Optional[T] = None,
    ):
        self.event_pipeline = event_pipeline
        self.state_pipeline = state_pipeline
        self.state = initial

        self.id = uuid.uuid4().__str__()

        event_pipeline.attach(FrameListener, self.supply)

    def supply(self, frame: Frame[Event]) -> None:
        if frame.data.event_type == EventType.UPDATE_STATE:
            self.state_pipeline.send(
                StateData(id=self.id, state=self.state), sender_id=self.id
            )

    def update(self, new: Optional[T]) -> None:
        self.state = new

    def get_id(self) -> str:
        return self.id


class PipelineState(Generic[T]):
    def __init__(self, id: str, state_pipeline: FramePipeline[StateData]) -> None:
        self.id = id
        self.state_pipeline = state_pipeline

        self.current: Optional[T] = None

        self.state_pipeline.attach(FrameListener, self.update)

    @classmethod
    def from_supplier(cls, supplier: PipelineSupplier) -> Self:
        return cls(supplier.get_id(), supplier.state_pipeline)

    def get(self) -> Optional[T]:
        return self.current

    def update(self, frame: Frame[StateData]) -> None:
        if frame.data.id == self.id:
            self.current = frame.data.state


class ManagedState(Generic[T]):
    def __init__(
        self,
        initial: T,
        event_pipeline: FramePipeline[Event],
        state_pipeline: FramePipeline[StateData],
    ) -> None:
        self.event_pipeline = event_pipeline
        self.state_pipeline = state_pipeline

        self.supplier = PipelineSupplier(
            self.event_pipeline, self.state_pipeline, initial
        )
        self.state = PipelineState.from_supplier(self.supplier)

    def get(self) -> Optional[T]:
        return self.state.get()

    def update(self, new: Optional[T]):
        self.supplier.update(new)
