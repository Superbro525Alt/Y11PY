#ifndef SDL_WRAPPER_H
#define SDL_WRAPPER_H

#include <SDL.h>
#include <SDL_ttf.h> // Include for text rendering
#include <string>
#include <vector>

class SDLWrapper {
public:
    SDLWrapper(int width, int height, const std::string& title);
    ~SDLWrapper();

    bool initialize();
    void createWindow();
    void createRenderer();
    void clearScreen(Uint8 r, Uint8 g, Uint8 b);
    void updateScreen();
    void drawRect(int x, int y, int w, int h, Uint8 r, Uint8 g, Uint8 b);

    // Drawing functions
    void drawLine(int x1, int y1, int x2, int y2, Uint8 r, Uint8 g, Uint8 b);
    void drawPoint(int x, int y, Uint8 r, Uint8 g, Uint8 b);
    void drawCircle(int centerX, int centerY, int radius, Uint8 r, Uint8 g, Uint8 b);
    void fillCircle(int centerX, int centerY, int radius, Uint8 r, Uint8 g, Uint8 b);
    void drawPolygon(const std::vector<std::pair<int, int>>& points, Uint8 r, Uint8 g, Uint8 b);
    void fillRect(int x, int y, int w, int h, Uint8 r, Uint8 g, Uint8 b);
    void drawTexture(SDL_Texture* texture, int x, int y);
    void drawTexture(SDL_Texture* texture, SDL_Rect* srcRect, SDL_Rect* dstRect);

    // Texture loading and manipulation
    SDL_Texture* loadTexture(const std::string& path);
    SDL_Texture* createTextureFromSurface(SDL_Surface* surface);
    SDL_Texture* createTexture(int width, int height);
    void freeTexture(SDL_Texture* texture);
    void setTextureBlendMode(SDL_Texture* texture, SDL_BlendMode blendMode);
    void setTextureAlphaMod(SDL_Texture* texture, Uint8 alpha);
    void setTextureColorMod(SDL_Texture* texture, Uint8 r, Uint8 g, Uint8 b);

    // Text rendering
    bool loadFont(const std::string& path, int size);
    void drawText(const std::string& text, int x, int y, SDL_Color color);
    void drawText(const std::string& text, int x, int y, Uint8 r, Uint8 g, Uint8 b);
    SDL_Rect getTextSize(const std::string& text);

    // Event handling
    bool pollEvent(SDL_Event& event);

    // Timing and delays
    Uint32 getTicks();
    void delay(Uint32 ms);

    // Input handling
    const Uint8* getKeyboardState(int* numkeys);
    bool isKeyPressed(SDL_Scancode key);

    // Getters
    SDL_Renderer* getRenderer() const;
    int getWidth() const;
    int getHeight() const;

    std::tuple<int, int> getMousePosition(); // Return tuple of x and y
    bool isMouseButtonDown(Uint8 button);
    bool isWindowFocused();

private:
    SDL_Window* window = nullptr;
    SDL_Renderer* renderer = nullptr;
    int width, height;
    std::string title;
    bool initialized = false;
    TTF_Font* font = nullptr;

    void _drawCircleHelper(int centerX, int centerY, int x, int y, Uint8 r, Uint8 g, Uint8 b);

};

#endif
