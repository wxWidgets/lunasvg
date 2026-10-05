/*
 * svgrender - minimal SVG -> PNG renderer for the wxlunasvg test suite.
 *
 * Usage:
 *   svgrender <input.svg> <output.png> [WIDTHxHEIGHT] [RRGGBBAA]
 *
 * Ports the single-file render mode of the out-of-tree prototype
 * (..\lunasvg-tests\src\test_svg_png.cpp): render one SVG to PNG at a chosen
 * size and background. Batch rendering and pixel comparison belong to the
 * golden-image engine (Phase 3) and are driven by ctest, not by this tool.
 */

#include <lunasvg.h>

#include <cstddef>
#include <cstdint>
#include <exception>
#include <iostream>
#include <memory>
#include <string>

static constexpr int PROGRAM_SUCCESS = 0;
static constexpr int PROGRAM_USAGE = 1;
static constexpr int PROGRAM_LOAD_FAILED = 2;
static constexpr int PROGRAM_RENDER_FAILED = 3;
static constexpr int PROGRAM_WRITE_FAILED = 4;

static constexpr std::uint32_t DEFAULT_BACKGROUND = 0x00000000U;

static void PrintUsage()
{
    std::cout << "Usage: svgrender <input.svg> <output.png> [WIDTHxHEIGHT] [RRGGBBAA]\n"
                 "Examples:\n"
                 "   svgrender input.svg output.png\n"
                 "   svgrender input.svg output.png 512x512\n"
                 "   svgrender input.svg output.png 512x512 112233FF\n";
}

static bool ParseSize(const std::string& text, int& width, int& height)
{
    const std::size_t separator = text.find('x');
    if(separator == std::string::npos || separator == 0 || (separator + 1) >= text.size()) {
        return false;
    }

    try {
        const int parsed_width = std::stoi(text.substr(0, separator));
        const int parsed_height = std::stoi(text.substr(separator + 1));
        if(parsed_width <= 0 || parsed_height <= 0) {
            return false;
        }
        width = parsed_width;
        height = parsed_height;
    } catch(const std::exception&) {
        return false;
    }

    return true;
}

static bool ParseColor(const std::string& text, std::uint32_t& color)
{
    std::string digits = text;
    if(digits.rfind("0x", 0) == 0 || digits.rfind("0X", 0) == 0) {
        digits = digits.substr(2);
    }
    if(digits.empty() || digits.size() > 8) {
        return false;
    }

    try {
        std::size_t consumed = 0;
        const unsigned long value = std::stoul(digits, &consumed, 16);
        if(consumed != digits.size()) {
            return false;
        }
        color = static_cast<std::uint32_t>(value);
    } catch(const std::exception&) {
        return false;
    }

    return true;
}

int main(int argc, char* argv[])
{
    if(argc < 3) {
        PrintUsage();
        return PROGRAM_USAGE;
    }

    const std::string input_path = argv[1];
    const std::string output_path = argv[2];
    int width = -1;
    int height = -1;
    std::uint32_t background = DEFAULT_BACKGROUND;

    if(argc > 3 && !ParseSize(argv[3], width, height)) {
        std::cerr << "error: invalid size '" << argv[3] << "' (expected WIDTHxHEIGHT, e.g. 512x512)\n";
        return PROGRAM_USAGE;
    }

    if(argc > 4 && !ParseColor(argv[4], background)) {
        std::cerr << "error: invalid background '" << argv[4] << "' (expected 8-digit hex RRGGBBAA)\n";
        return PROGRAM_USAGE;
    }

    const std::unique_ptr<wxlunasvg::Document> document = wxlunasvg::Document::loadFromFile(input_path);
    if(document == nullptr) {
        std::cerr << "error: failed to load SVG: " << input_path << "\n";
        return PROGRAM_LOAD_FAILED;
    }

    const wxlunasvg::Bitmap bitmap = document->renderToBitmap(width, height, background);
    if(bitmap.isNull()) {
        std::cerr << "error: failed to render SVG: " << input_path << "\n";
        return PROGRAM_RENDER_FAILED;
    }

    if(!bitmap.writeToPng(output_path)) {
        std::cerr << "error: failed to write PNG: " << output_path << "\n";
        return PROGRAM_WRITE_FAILED;
    }

    std::cout << "wrote " << output_path << " (" << bitmap.width() << "x" << bitmap.height() << ")\n";
    return PROGRAM_SUCCESS;
}
