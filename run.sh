#!/bin/bash

# Check if the --py flag is present
if [[ "$@" == *"--py"* ]]; then
  # Only run the Python script
  python src/main.py
else
  # Run both the make command and the Python script
  cd src/sdl-wrapper/ && make
  cd ../../ && python src/main.py
fi
