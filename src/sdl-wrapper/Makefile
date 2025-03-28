# Detect OS properly
ifeq ($(OS), Windows_NT)
	OS_TYPE := Windows
	PYTHON := python
	RM := powershell -Command "Get-Item -Path $(OUTPUT), compile_commands.json -ErrorAction SilentlyContinue | Remove-Item -Force"
else
	OS_TYPE := $(shell uname -s)
	PYTHON := python3
	RM := rm -f
endif

# Get Python includes & extension suffix
PYTHON_INCLUDES := $(shell $(PYTHON) -m pybind11 --includes)
PYTHON_SUFFIX := $(shell $(PYTHON) -c "import sysconfig; print(sysconfig.get_config_var('EXT_SUFFIX'))")

# Compiler and Flags
CXX := g++
CXXFLAGS := -O3 -Wall -std=c++17 -fPIC
SRC := $(wildcard *.cpp)  # Works on Windows
OUTPUT := ../bindings$(PYTHON_SUFFIX)

# SDL2 Paths
ifeq ($(OS_TYPE), Linux)
    SDL_FLAGS := `sdl2-config --cflags --libs` -lSDL2_ttf -lSDL2_image
    LDFLAGS := -shared -Wl,-rpath,'$$ORIGIN'
endif

ifeq ($(OS_TYPE), Darwin)
    SDL_FLAGS := `sdl2-config --cflags --libs` -lSDL2_ttf -lSDL2_image
    LDFLAGS := -dynamiclib -Wl,-rpath,'@loader_path'
endif

ifeq ($(OS_TYPE), Windows)
    SDL2_DIR := C:/SDL2 # Change this to your actual SDL2 installation path
    SDL_FLAGS := -IC:/SDL2/include/SDL2 -Dmain=SDL_main -LC:/SDL2/lib -lmingw32 -lSDL2main -lSDL2 -mwindows -lSDL2_ttf -lSDL2_image -static -luser32 -lgdi32 -lwinmm -limm32 -lole32 -loleaut32 -lshell32 -lsetupapi -lversion -lrpcrt4
    LDFLAGS := -shared -LC:\Users\paulh\AppData\Local\Programs\Python\Python312\libs -lpython312 -static
endif# Build Target
all: bindings

bindings:
	$(CXX) $(CXXFLAGS) $(PYTHON_INCLUDES) $(SRC) -o $(OUTPUT) $(LDFLAGS) $(SDL_FLAGS)
	cd .. && stubgen -m bindings -o .

# Generate compile_commands.json
compile_commands.json:
	bear -- make

# Clean target (cross-platform)
clean:
	$(RM)
