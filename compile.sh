mkdir -p release

nuitka --standalone --onefile --follow-imports src/server.py -o server_linux &
nuitka --standalone --onefile --follow-imports src/client.py -o client_linux &

wait

mv server_linux client_linux server.exe client.exe release/
