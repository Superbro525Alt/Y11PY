all: bindings

bindings:
	g++ -O3 -Wall -shared -std=c++17 -fPIC $(shell python3 -m pybind11 --includes) \
		$(shell find . -name "*.cpp") -o ../bindings$(shell python3-config --extension-suffix) \
		`sdl2-config --cflags --libs` -lSDL2_ttf -lSDL2_image -Wl,-rpath,'$$ORIGIN'
	cd .. && stubgen -m bindings -o .  

compile_commands.json:
	bear -- make

clean:
	rm -f bindings$(shell python3-config --extension-suffix) compile_commands.json

.PHONY: all clean compile_commands.json
