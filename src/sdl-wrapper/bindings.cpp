#include "SDL_mouse.h"
#include "wrapper.h" // Your SDLWrapper header file
#include <pybind11/pybind11.h>
#include <SDL_render.h> // You might need this for other functions
#include <SDL_surface.h> // Likely this one for SDL_Texture definition
#include "SDL_stdinc.h"
#include <cmath> // For circle drawing
#include <SDL.h>
#include <SDL_ttf.h> // For text rendering
#include <SDL_image.h> // For image loading (if you use it)
#include <string>
#include <vector>
#include <utility> // For std::pair
#include <pybind11/stl.h> // Include for STL container support

namespace py = pybind11;

PYBIND11_MODULE(bindings, m) {
    m.doc() = "Python wrapper for SDL2";

    py::class_<SDLWrapper>(m, "SDLWrapper")
        .def(py::init<int, int, const std::string&>(), "Constructor for SDLWrapper")
        .def("initialize", &SDLWrapper::initialize, "Initializes SDL")
        .def("create_window", &SDLWrapper::createWindow, "Creates the SDL window")
        .def("create_renderer", &SDLWrapper::createRenderer, "Creates the SDL renderer")
        .def("clear_screen", &SDLWrapper::clearScreen, "Clears the screen")
        .def("update_screen", &SDLWrapper::updateScreen, "Updates the screen")
        .def("draw_rect", &SDLWrapper::drawRect, "Draws a rectangle",
             py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"),
             py::arg("r"), py::arg("g"), py::arg("b"))  // Named arguments

        .def("draw_line", &SDLWrapper::drawLine, "Draws a line",
             py::arg("x1"), py::arg("y1"), py::arg("x2"), py::arg("y2"),
             py::arg("r"), py::arg("g"), py::arg("b"))

        .def("draw_point", &SDLWrapper::drawPoint, "Draws a point",
             py::arg("x"), py::arg("y"), py::arg("r"), py::arg("g"), py::arg("b"))

        .def("draw_circle", &SDLWrapper::drawCircle, "Draws a circle",
             py::arg("centerX"), py::arg("centerY"), py::arg("radius"),
             py::arg("r"), py::arg("g"), py::arg("b"))

        .def("fill_circle", &SDLWrapper::fillCircle, "Fills a circle",
             py::arg("centerX"), py::arg("centerY"), py::arg("radius"),
             py::arg("r"), py::arg("g"), py::arg("b"))

        .def("draw_polygon", &SDLWrapper::drawPolygon, "Draws a polygon",
             py::arg("points"), py::arg("r"), py::arg("g"), py::arg("b"))

        .def("fill_rect", &SDLWrapper::fillRect, "Fills a rectangle",
             py::arg("x"), py::arg("y"), py::arg("w"), py::arg("h"),
             py::arg("r"), py::arg("g"), py::arg("b"))

        // .def("load_texture", &SDLWrapper::loadTexture, "Loads a texture", py::arg("path"))
        // .def("draw_texture", py::overload_cast<SDL_Texture*, int, int>(&SDLWrapper::drawTexture), "Draws a texture", py::arg("texture"), py::arg("x"), py::arg("y"))
        // .def("draw_texture", py::overload_cast<SDL_Texture*, SDL_Rect*, SDL_Rect*>(&SDLWrapper::drawTexture), "Draws a texture with source and destination rectangles", py::arg("texture"), py::arg("srcRect"), py::arg("dstRect"))
        // .def("free_texture", &SDLWrapper::freeTexture, "Frees a texture", py::arg("texture"))
        // .def("set_texture_blend_mode", &SDLWrapper::setTextureBlendMode, "Sets texture blend mode", py::arg("texture"), py::arg("blendMode"))
        // .def("set_texture_alpha_mod", &SDLWrapper::setTextureAlphaMod, "Sets texture alpha modulation", py::arg("texture"), py::arg("alpha"))
        // .def("set_texture_color_mod", &SDLWrapper::setTextureColorMod, "Sets texture color modulation", py::arg("texture"), py::arg("r"), py::arg("g"), py::arg("b"))
        //
        .def("load_font", &SDLWrapper::loadFont, "Loads a font", py::arg("path"), py::arg("size"))
        .def("draw_text", py::overload_cast<const std::string&, int, int, SDL_Color>(&SDLWrapper::drawText), "Draws text with SDL_Color", py::arg("text"), py::arg("x"), py::arg("y"), py::arg("color"))
        .def("draw_text", py::overload_cast<const std::string&, int, int, Uint8, Uint8, Uint8>(&SDLWrapper::drawText), "Draws text with RGB", py::arg("text"), py::arg("x"), py::arg("y"), py::arg("r"), py::arg("g"), py::arg("b"))
          .def("get_text_size", &SDLWrapper::getTextSize, "Gets text size", py::arg("text")) // Corrected name

        .def("poll_event", &SDLWrapper::pollEvent, "Polls for events", py::arg("event"))  // Important:  See explanation below

        .def("get_ticks", &SDLWrapper::getTicks, "Gets SDL ticks")
        .def("delay", &SDLWrapper::delay, "Delays execution")
        .def("is_key_pressed", &SDLWrapper::isKeyPressed, "Checks if a key is pressed", py::arg("key"))

        .def("get_width", &SDLWrapper::getWidth, "Gets window width")
        .def("get_height", &SDLWrapper::getHeight, "Gets window height")
        .def("getMousePosition", &SDLWrapper::getMousePosition, "Get mouse position (relative to center)")
        .def("is_mouse_button_down", &SDLWrapper::isMouseButtonDown, "Checks if a mouse button is pressed", py::arg("button"))
    .def("is_window_focused", &SDLWrapper::isWindowFocused, "Checks if the SDL window is focused");

    // Example of how to bind an enum
    py::enum_<SDL_BlendMode>(m, "BlendMode")
        .value("BLEND", SDL_BLENDMODE_BLEND)
        .value("ADD", SDL_BLENDMODE_ADD)
        .value("MOD", SDL_BLENDMODE_MOD)
        .value("NONE", SDL_BLENDMODE_NONE)
        .export_values();

    // Example: Bind SDL_Color struct
    py::class_<SDL_Color>(m, "Color")
        .def(py::init<Uint8, Uint8, Uint8, Uint8>())
        .def_readwrite("r", &SDL_Color::r)
        .def_readwrite("g", &SDL_Color::g)
        .def_readwrite("b", &SDL_Color::b)
        .def_readwrite("a", &SDL_Color::a);

    // Example: Bind SDL_Rect struct
    py::class_<SDL_Rect>(m, "SDL_Rect")
        .def(py::init<int, int, int, int>())
        .def_readwrite("x", &SDL_Rect::x)
        .def_readwrite("y", &SDL_Rect::y)
        .def_readwrite("w", &SDL_Rect::w)
        .def_readwrite("h", &SDL_Rect::h);

py::enum_<SDL_Scancode>(m, "SDL_Scancode")
        .value("Unknown", SDL_SCANCODE_UNKNOWN)
        .value("A", SDL_SCANCODE_A)
        .value("B", SDL_SCANCODE_B)
        .value("C", SDL_SCANCODE_C)
        .value("D", SDL_SCANCODE_D)
        .value("E", SDL_SCANCODE_E)
        .value("F", SDL_SCANCODE_F)
        .value("G", SDL_SCANCODE_G)
        .value("H", SDL_SCANCODE_H)
        .value("I", SDL_SCANCODE_I)
        .value("J", SDL_SCANCODE_J)
        .value("K", SDL_SCANCODE_K)
        .value("L", SDL_SCANCODE_L)
        .value("M", SDL_SCANCODE_M)
        .value("N", SDL_SCANCODE_N)
        .value("O", SDL_SCANCODE_O)
        .value("P", SDL_SCANCODE_P)
        .value("Q", SDL_SCANCODE_Q)
        .value("R", SDL_SCANCODE_R)
        .value("S", SDL_SCANCODE_S)
        .value("T", SDL_SCANCODE_T)
        .value("U", SDL_SCANCODE_U)
        .value("V", SDL_SCANCODE_V)
        .value("W", SDL_SCANCODE_W)
        .value("X", SDL_SCANCODE_X)
        .value("Y", SDL_SCANCODE_Y)
        .value("Z", SDL_SCANCODE_Z)
        .value("One", SDL_SCANCODE_1)
        .value("Two", SDL_SCANCODE_2)
        .value("Three", SDL_SCANCODE_3)
        .value("Four", SDL_SCANCODE_4)
        .value("Five", SDL_SCANCODE_5)
        .value("Six", SDL_SCANCODE_6)
        .value("Seven", SDL_SCANCODE_7)
        .value("Eight", SDL_SCANCODE_8)
        .value("Nine", SDL_SCANCODE_9)
        .value("Zero", SDL_SCANCODE_0)
        .value("Return", SDL_SCANCODE_RETURN)
        .value("Escape", SDL_SCANCODE_ESCAPE)
        .value("Backspace", SDL_SCANCODE_BACKSPACE)
        .value("Tab", SDL_SCANCODE_TAB)
        .value("Space", SDL_SCANCODE_SPACE)
        .value("Minus", SDL_SCANCODE_MINUS)
        .value("Equals", SDL_SCANCODE_EQUALS)
        .value("LeftBracket", SDL_SCANCODE_LEFTBRACKET)
        .value("RightBracket", SDL_SCANCODE_RIGHTBRACKET)
        .value("Backslash", SDL_SCANCODE_BACKSLASH)
        .value("Semicolon", SDL_SCANCODE_SEMICOLON)
        .value("Apostrophe", SDL_SCANCODE_APOSTROPHE)
        .value("Grave", SDL_SCANCODE_GRAVE)
        .value("Comma", SDL_SCANCODE_COMMA)
        .value("Period", SDL_SCANCODE_PERIOD)
        .value("Slash", SDL_SCANCODE_SLASH)
        .value("CapsLock", SDL_SCANCODE_CAPSLOCK)
        .value("F1", SDL_SCANCODE_F1)
        .value("F2", SDL_SCANCODE_F2)
        .value("F3", SDL_SCANCODE_F3)
        .value("F4", SDL_SCANCODE_F4)
        .value("F5", SDL_SCANCODE_F5)
        .value("F6", SDL_SCANCODE_F6)
        .value("F7", SDL_SCANCODE_F7)
        .value("F8", SDL_SCANCODE_F8)
        .value("F9", SDL_SCANCODE_F9)
        .value("F10", SDL_SCANCODE_F10)
        .value("F11", SDL_SCANCODE_F11)
        .value("F12", SDL_SCANCODE_F12)
        .value("Right", SDL_SCANCODE_RIGHT)  // Added Right Arrow
        .value("Left", SDL_SCANCODE_LEFT)    // Added Left Arrow
        .value("Down", SDL_SCANCODE_DOWN)   // Added Down Arrow
        .value("Up", SDL_SCANCODE_UP)     // Added Up Arrow
        .export_values();

      py::class_<SDL_Event>(m, "SDL_Event")
        .def(py::init<>())
        .def_readwrite("type", &SDL_Event::type)
        .def_readwrite("key", &SDL_Event::key)
        .def_readwrite("motion", &SDL_Event::motion)
        .def_readwrite("button", &SDL_Event::button)
        .def_readwrite("window", &SDL_Event::window)
        .def_readwrite("quit", &SDL_Event::quit)
        .def_readwrite("user", &SDL_Event::user)
        .def_readwrite("jdevice", &SDL_Event::jdevice)
        .def_readwrite("cdevice", &SDL_Event::cdevice)
        .def_readwrite("sensor", &SDL_Event::sensor)
        .def_readwrite("adevice", &SDL_Event::adevice);

    py::class_<SDL_KeyboardEvent>(m, "SDL_KeyboardEvent")
        .def_readwrite("type", &SDL_KeyboardEvent::type)
        .def_readwrite("timestamp", &SDL_KeyboardEvent::timestamp)
        .def_readwrite("windowID", &SDL_KeyboardEvent::windowID)
        .def_readwrite("state", &SDL_KeyboardEvent::state)
        .def_readwrite("repeat", &SDL_KeyboardEvent::repeat)
        .def_readwrite("keysym", &SDL_KeyboardEvent::keysym);

    py::class_<SDL_MouseMotionEvent>(m, "SDL_MouseMotionEvent")
        .def_readwrite("type", &SDL_MouseMotionEvent::type)
        .def_readwrite("timestamp", &SDL_MouseMotionEvent::timestamp)
        .def_readwrite("windowID", &SDL_MouseMotionEvent::windowID)
        .def_readwrite("which", &SDL_MouseMotionEvent::which)
        .def_readwrite("state", &SDL_MouseMotionEvent::state)
        .def_readwrite("x", &SDL_MouseMotionEvent::x)
        .def_readwrite("y", &SDL_MouseMotionEvent::y)
        .def_readwrite("xrel", &SDL_MouseMotionEvent::xrel)
        .def_readwrite("yrel", &SDL_MouseMotionEvent::yrel);

    py::class_<SDL_MouseButtonEvent>(m, "SDL_MouseButtonEvent")
        .def_readwrite("type", &SDL_MouseButtonEvent::type)
        .def_readwrite("timestamp", &SDL_MouseButtonEvent::timestamp)
        .def_readwrite("windowID", &SDL_MouseButtonEvent::windowID)
        .def_readwrite("which", &SDL_MouseButtonEvent::which)
        .def_readwrite("button", &SDL_MouseButtonEvent::button)
        .def_readwrite("state", &SDL_MouseButtonEvent::state)
        .def_readwrite("x", &SDL_MouseButtonEvent::x)
        .def_readwrite("y", &SDL_MouseButtonEvent::y);

    py::class_<SDL_WindowEvent>(m, "SDL_WindowEvent")
        .def_readwrite("type", &SDL_WindowEvent::type)
        .def_readwrite("timestamp", &SDL_WindowEvent::timestamp)
        .def_readwrite("windowID", &SDL_WindowEvent::windowID)
        .def_readwrite("event", &SDL_WindowEvent::event)
        .def_readwrite("data1", &SDL_WindowEvent::data1)
        .def_readwrite("data2", &SDL_WindowEvent::data2);

    py::class_<SDL_QuitEvent>(m, "SDL_QuitEvent")
        .def_readwrite("type", &SDL_QuitEvent::type)
        .def_readwrite("timestamp", &SDL_QuitEvent::timestamp);

    py::class_<SDL_UserEvent>(m, "SDL_UserEvent")
        .def_readwrite("type", &SDL_UserEvent::type)
        .def_readwrite("timestamp", &SDL_UserEvent::timestamp)
        .def_readwrite("windowID", &SDL_UserEvent::windowID)
        .def_readwrite("code", &SDL_UserEvent::code)
        .def_readwrite("data1", &SDL_UserEvent::data1)
        .def_readwrite("data2", &SDL_UserEvent::data2);

    py::class_<SDL_JoyDeviceEvent>(m, "SDL_JoyDeviceEvent")
        .def_readwrite("type", &SDL_JoyDeviceEvent::type)
        .def_readwrite("timestamp", &SDL_JoyDeviceEvent::timestamp)
        .def_readwrite("which", &SDL_JoyDeviceEvent::which);

    py::class_<SDL_ControllerDeviceEvent>(m, "SDL_ControllerDeviceEvent")
        .def_readwrite("type", &SDL_ControllerDeviceEvent::type)
        .def_readwrite("timestamp", &SDL_ControllerDeviceEvent::timestamp)
        .def_readwrite("which", &SDL_ControllerDeviceEvent::which);

    py::class_<SDL_SensorEvent>(m, "SDL_SensorEvent")
        .def_readwrite("type", &SDL_SensorEvent::type)
        .def_readwrite("timestamp", &SDL_SensorEvent::timestamp)
        .def_readwrite("which", &SDL_SensorEvent::which);

    py::class_<SDL_AudioDeviceEvent>(m, "SDL_AudioDeviceEvent")
        .def_readwrite("type", &SDL_AudioDeviceEvent::type)
        .def_readwrite("timestamp", &SDL_AudioDeviceEvent::timestamp)
        .def_readwrite("which", &SDL_AudioDeviceEvent::which)
        .def_readwrite("iscapture", &SDL_AudioDeviceEvent::iscapture);

    py::class_<SDL_Keysym>(m, "SDL_Keysym")
        .def_readwrite("scancode", &SDL_Keysym::scancode)
        .def_readwrite("sym", &SDL_Keysym::sym)
        .def_readwrite("mod", &SDL_Keysym::mod)
        .def_readwrite("unused", &SDL_Keysym::unused);

      py::enum_<SDL_EventType>(m, "SDL_EventType")
        .value("QUIT", SDL_QUIT)
        .value("KEYDOWN", SDL_KEYDOWN)
        .value("KEYUP", SDL_KEYUP)
        .value("MOUSEMOTION", SDL_MOUSEMOTION)
        .value("MOUSEBUTTONDOWN", SDL_MOUSEBUTTONDOWN)
        .value("MOUSEBUTTONUP", SDL_MOUSEBUTTONUP)
        .value("WINDOWEVENT", SDL_WINDOWEVENT)
        .value("JOYDEVICEADDED", SDL_JOYDEVICEADDED)
        .value("JOYDEVICEREMOVED", SDL_JOYDEVICEREMOVED)
        .value("JOYAXISMOTION", SDL_JOYAXISMOTION)
        .value("JOYBALLMOTION", SDL_JOYBALLMOTION)
        .value("JOYHATMOTION", SDL_JOYHATMOTION)
        .value("JOYBUTTONDOWN", SDL_JOYBUTTONDOWN)
        .value("JOYBUTTONUP", SDL_JOYBUTTONUP)
        .value("CONTROLLERDEVICEADDED", SDL_CONTROLLERDEVICEADDED)
        .value("CONTROLLERDEVICEREMOVED", SDL_CONTROLLERDEVICEREMOVED)
        .value("CONTROLLERAXISMOTION", SDL_CONTROLLERAXISMOTION)
        .value("CONTROLLERBUTTONDOWN", SDL_CONTROLLERBUTTONDOWN)
        .value("CONTROLLERBUTTONUP", SDL_CONTROLLERBUTTONUP)
        .value("SENSORUPDATE", SDL_SENSORUPDATE)
        .value("AUDIODEVICEADDED", SDL_AUDIODEVICEADDED)
        .value("AUDIODEVICEREMOVED", SDL_AUDIODEVICEREMOVED)
        // Add all required SDL_EventType values.
        .export_values();

  m.attr("SDL_BUTTON_LEFT") = SDL_BUTTON_LEFT;
m.attr("SDL_BUTTON_MIDDLE") = SDL_BUTTON_MIDDLE;
m.attr("SDL_BUTTON_RIGHT") = SDL_BUTTON_RIGHT;
m.attr("SDL_BUTTON_X1") = SDL_BUTTON_X1;
m.attr("SDL_BUTTON_X2") = SDL_BUTTON_X2;


}
