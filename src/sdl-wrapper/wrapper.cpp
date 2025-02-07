#include "wrapper.h"
#include "SDL_stdinc.h"
#include <cmath> // For circle drawing
#include <SDL.h>
#include <SDL_ttf.h> // For text rendering
#include <SDL_image.h> // For image loading (if you use it)
#include <string>
#include <vector>

SDLWrapper::SDLWrapper(int width, int height, const std::string& title) :
    width(width), height(height), title(title) {}

SDLWrapper::~SDLWrapper() {
    if (renderer) {
        SDL_DestroyRenderer(renderer);
    }
    if (window) {
        SDL_DestroyWindow(window);
    }
    if (font) {
        TTF_CloseFont(font);
    }
    TTF_Quit();
    SDL_Quit();
}

bool SDLWrapper::initialize() {
    if (SDL_Init(SDL_INIT_VIDEO) < 0) {
        SDL_Log("SDL could not initialize! SDL Error: %s\n", SDL_GetError());
        return false;
    }

    if (TTF_Init() < 0) {
        SDL_Log("TTF could not initialize! TTF Error: %s\n", TTF_GetError());
        return false;
    }

    initialized = true;
    return true;
}

void SDLWrapper::createWindow() {
    if (!initialized) return;

    window = SDL_CreateWindow(title.c_str(), SDL_WINDOWPOS_UNDEFINED, SDL_WINDOWPOS_UNDEFINED, width, height, SDL_WINDOW_SHOWN);
    if (window == nullptr) {
        SDL_Log("Window could not be created! SDL Error: %s\n", SDL_GetError());
    }
}

void SDLWrapper::createRenderer() {
     if (!window) return;
    renderer = SDL_CreateRenderer(window, -1, SDL_RENDERER_SOFTWARE); // Use hardware acceleration if available
    if (renderer == nullptr) {
        SDL_Log("Renderer could not be created! SDL Error: %s\n", SDL_GetError());
    }
}


void SDLWrapper::clearScreen(Uint8 r, Uint8 g, Uint8 b) {
    SDL_SetRenderDrawColor(renderer, r, g, b, 255);
    SDL_RenderClear(renderer);
}

void SDLWrapper::updateScreen() {
    SDL_RenderPresent(renderer);
}

void SDLWrapper::drawRect(int x, int y, int w, int h, Uint8 r, Uint8 g, Uint8 b) {
    SDL_SetRenderDrawColor(renderer, r, g, b, 255);
    SDL_Rect rect = { x, y, w, h };
    SDL_RenderDrawRect(renderer, &rect);
}

void SDLWrapper::drawLine(int x1, int y1, int x2, int y2, Uint8 r, Uint8 g, Uint8 b) {
    SDL_SetRenderDrawColor(renderer, r, g, b, 255);
    SDL_RenderDrawLine(renderer, x1, y1, x2, y2);
}

void SDLWrapper::drawPoint(int x, int y, Uint8 r, Uint8 g, Uint8 b) {
    SDL_SetRenderDrawColor(renderer, r, g, b, 255);
    SDL_RenderDrawPoint(renderer, x, y);
}

void SDLWrapper::drawCircle(int centerX, int centerY, int radius, Uint8 r, Uint8 g, Uint8 b) {
    _drawCircleHelper(centerX, centerY, radius, 0, r, g, b);
}

void SDLWrapper::fillCircle(int centerX, int centerY, int radius, Uint8 r, Uint8 g, Uint8 b) {
    for (int y = -radius; y <= radius; y++) {
        for (int x = -radius; x <= radius; x++) {
            if (x * x + y * y <= radius * radius) {
                drawPoint(centerX + x, centerY + y, r, g, b);
            }
        }
    }
}

void SDLWrapper::_drawCircleHelper(int centerX, int centerY, int x, int y, Uint8 r, Uint8 g, Uint8 b) {
    if (x > y)
        return;

    drawPoint(centerX + x, centerY + y, r, g, b);
    drawPoint(centerX + y, centerY + x, r, g, b);
    drawPoint(centerX - x, centerY + y, r, g, b);
    drawPoint(centerX - y, centerY + x, r, g, b);
    drawPoint(centerX + x, centerY - y, r, g, b);
    drawPoint(centerX + y, centerY - x, r, g, b);
    drawPoint(centerX - x, centerY - y, r, g, b);
    drawPoint(centerX - y, centerY - x, r, g, b);

    _drawCircleHelper(centerX, centerY, x + 1, y, r, g, b); // Corrected recursion
    if (x < y) {
        _drawCircleHelper(centerX, centerY, x, y - 1, r, g, b);
    }


}



void SDLWrapper::drawPolygon(const std::vector<std::pair<int, int>>& points, Uint8 r, Uint8 g, Uint8 b) {
    if (points.size() < 2) return;

    SDL_SetRenderDrawColor(renderer, r, g, b, 255);
    for (size_t i = 0; i < points.size() - 1; ++i) {
        SDL_RenderDrawLine(renderer, points[i].first, points[i].second, points[i + 1].first, points[i + 1].second);
    }
    SDL_RenderDrawLine(renderer, points.back().first, points.back().second, points.front().first, points.front().second); // Close the polygon
}

void SDLWrapper::fillRect(int x, int y, int w, int h, Uint8 r, Uint8 g, Uint8 b) {
    SDL_SetRenderDrawColor(renderer, r, g, b, 255);
    SDL_Rect rect = { x, y, w, h };
    SDL_RenderFillRect(renderer, &rect);
}


SDL_Texture* SDLWrapper::loadTexture(const std::string& path) {
    SDL_Texture* texture = nullptr;
    SDL_Surface* loadedSurface = IMG_Load(path.c_str()); // Requires SDL_image
    if (loadedSurface == nullptr) {
        SDL_Log("Unable to load image %s! SDL_image Error: %s\n", path.c_str(), IMG_GetError());
    } else {
        texture = SDL_CreateTextureFromSurface(renderer, loadedSurface);
        if (texture == nullptr) {
            SDL_Log("Unable to create texture from %s! SDL Error: %s\n", path.c_str(), SDL_GetError());
        }
        SDL_FreeSurface(loadedSurface);
    }
    return texture;
}

SDL_Texture* SDLWrapper::createTextureFromSurface(SDL_Surface* surface) {
    return SDL_CreateTextureFromSurface(renderer, surface);
}

SDL_Texture* SDLWrapper::createTexture(int width, int height) {
    return SDL_CreateTexture(renderer, SDL_PIXELFORMAT_RGBA8888, SDL_TEXTUREACCESS_TARGET, width, height);
}

void SDLWrapper::freeTexture(SDL_Texture* texture) {
    if (texture) {
        SDL_DestroyTexture(texture);
    }
}

void SDLWrapper::setTextureBlendMode(SDL_Texture* texture, SDL_BlendMode blendMode) {
    SDL_SetTextureBlendMode(texture, blendMode);
}

void SDLWrapper::setTextureAlphaMod(SDL_Texture* texture, Uint8 alpha) {
    SDL_SetTextureAlphaMod(texture, alpha);
}

void SDLWrapper::setTextureColorMod(SDL_Texture* texture, Uint8 r, Uint8 g, Uint8 b) {
    SDL_SetTextureColorMod(texture, r, g, b);
}

void SDLWrapper::drawTexture(SDL_Texture* texture, int x, int y) {
    SDL_Rect dstRect = { x, y, 0, 0 };
    SDL_QueryTexture(texture, nullptr, nullptr, &dstRect.w, &dstRect.h); // Get texture dimensions
    SDL_RenderCopy(renderer, texture, nullptr, &dstRect);
}

void SDLWrapper::drawTexture(SDL_Texture* texture, SDL_Rect* srcRect, SDL_Rect* dstRect) {
    SDL_RenderCopy(renderer, texture, srcRect, dstRect);
}

bool SDLWrapper::loadFont(const std::string& path, int size) {
    font = TTF_OpenFont(path.c_str(), size);
    if (font == nullptr) {
        SDL_Log("Failed to load font! TTF Error: %s\n", TTF_GetError());
        return false;
    }
    return true;
}

void SDLWrapper::drawText(const std::string& text, int x, int y, SDL_Color color) {
    if (font == nullptr) {
        SDL_Log("Cannot draw text: Font not loaded!\n");
        return;
    }

    SDL_Surface* textSurface = TTF_RenderText_Solid(font, text.c_str(), color);
    if (textSurface == nullptr) {
        SDL_Log("Unable to render text surface!  TTF Error: %s\n", TTF_GetError());
        return;
    }

    SDL_Texture* texture = SDL_CreateTextureFromSurface(renderer, textSurface);
    if (texture == nullptr) {
        SDL_Log("Unable to create texture from rendered text! SDL Error: %s\n", SDL_GetError());
    } else {
        SDL_Rect dstRect = { x, y, textSurface->w, textSurface->h };
        SDL_RenderCopy(renderer, texture, nullptr, &dstRect);
        SDL_DestroyTexture(texture);
    }

    SDL_FreeSurface(textSurface);
}

void SDLWrapper::drawText(const std::string& text, int x, int y, Uint8 r, Uint8 g, Uint8 b) {
    SDL_Color color = { r, g, b, 255 };
    drawText(text, x, y, color);
}


SDL_Rect SDLWrapper::getTextSize(const std::string& text) {
    SDL_Rect rect = {0, 0, 0, 0};
    if (font) {
        TTF_SizeText(font, text.c_str(), &rect.w, &rect.h);
    } else {
        SDL_Log("Cannot get text size: Font not loaded!\n");
    }
    return rect;
}

bool SDLWrapper::pollEvent(SDL_Event& event) {
    return SDL_PollEvent(&event) != 0;
}

Uint32 SDLWrapper::getTicks() {
    return SDL_GetTicks();
}

void SDLWrapper::delay(Uint32 ms) {
    SDL_Delay(ms);
}

const Uint8* SDLWrapper::getKeyboardState(int* numkeys) {
    return SDL_GetKeyboardState(numkeys);
}

bool SDLWrapper::isKeyPressed(SDL_Scancode key) {
    int numkeys;
    const Uint8* keyboardState = SDL_GetKeyboardState(&numkeys);
    if (keyboardState) {
        return keyboardState[key];
    }
    return false;
}

SDL_Renderer* SDLWrapper::getRenderer() const {
    return renderer;
}

int SDLWrapper::getWidth() const {
    return width;
}

int SDLWrapper::getHeight() const {
    return height;
}
