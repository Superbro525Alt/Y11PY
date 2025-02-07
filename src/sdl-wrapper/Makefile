# Default target
all: bindings

bindings: libwrapper.so
	g++ -O3 -Wall -shared -std=c++17 -fPIC $(shell python3 -m pybind11 --includes) bindings.cpp -o ../bindings$(shell python3-config --extension-suffix) -L. -lwrapper `sdl2-config --cflags --libs` -lSDL2_ttf -lSDL2_image -Wl,-rpath,'$$ORIGIN'
	cd .. && stubgen -m bindings -o .  # Assuming 'bindings' is the name of your module

libwrapper.so: $(shell find . -name "*.cpp" -not -name "bindings.cpp") $(shell find . -name "*.h")
	g++ -O3 -Wall -shared -std=c++17 -fPIC $(shell find . -name "*.cpp" -not -name "bindings.cpp") -o libwrapper.so `sdl2-config --cflags --libs` -lSDL2_ttf -lSDL2_image -Wl,-rpath,'$$ORIGIN'
	cp libwrapper.so ../

# Compile commands generation (using Bear)
compile_commands.json:
	bear -- make

# Clean target
clean:
	rm -f bindings$(shell python3-config --extension-suffix) libwrapper.so compile_commands.json ../libwrapper.so

# Phony targets
.PHONY: all clean compile_commands.json
# all: lib target 
#
# target: lib
# 	c++ -O3 -Wall -shared -std=c++11 -fPIC $(shell python3 -m pybind11 --includes) bindings.cpp -o ../bindings$(shell python3-config --extension-suffix) `sdl2-config --cflags --libs` -L. libwrapper.a
#
# lib:
# 	g++ -shared -o wrapper.o $(shell find . -name "*.cpp" -not -name "bindings.cpp") $(shell find . -name "*.h") -Wl,-soname,wrapper.o -lc -ldl -lpthread -lm `sdl2-config --cflags --libs` -fPIC
# 	ar rcs libwrapper.a wrapper.o # Create the static archive
# # Rule to compile the shared library
# # target:
# # 	c++ -O3 -Wall -shared -std=c++11 -fPIC $(python3 -m pybind11 --includes) bindings.cpp -o bindings$(python3-config --extension-suffix)
#
# # Compile commands generation (using Bear)
# compile_commands.json: 
# 	bear -- make
#
# # Clean target
# clean:
# 	rm -f $(TARGET) compile_commands.json *.o # Added compile_commands.json and .o files
#
# # Phony targets
# .PHONY: all clean compile_commands.json
