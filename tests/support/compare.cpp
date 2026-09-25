/*
 * Implementation of the golden-image comparison engine (plan Phase 3).
 *
 * The PNG reader is the vendored stb_image v2.30 (public domain / MIT) noted
 * in tests/data/provenance.md. STB_IMAGE_STATIC keeps every stb symbol
 * file-local - exactly how plutovg vendors the same header into
 * plutovg/source/plutovg-surface.c - so nothing leaks out of the test binary
 * and no symbol can collide with the library's private copy. STBI_ONLY_PNG
 * trims the decoder to PNG and STBI_NO_STDIO drops the file/wchar helpers we do
 * not use (we read the bytes ourselves and decode from memory).
 *
 * The diff PNG is written through the library's own Bitmap::writeToPng rather
 * than a second writer dependency.
 */

#include "compare.h"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <fstream>
#include <iomanip>
#include <iterator>
#include <sstream>
#include <string>
#include <utility>
#include <vector>

#include <lunasvg.h>

#define STB_IMAGE_STATIC
#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_PNG
#define STBI_NO_STDIO
#include "stb_image.h"

namespace wxlunasvg {
namespace test {

namespace {

constexpr std::size_t RGBA_CHANNELS = 4U;
constexpr std::size_t RGB_CHANNELS = 3U;

// Slack used when comparing the differing-pixel fraction against the allowed
// ratio, so a ratio of exactly zero still accepts an exact match.
constexpr double RATIO_EPSILON = 1e-9;

std::uint32_t PackRgba(const std::uint8_t* pixel)
{
    return (static_cast<std::uint32_t>(pixel[0]) << 24U)
         | (static_cast<std::uint32_t>(pixel[1]) << 16U)
         | (static_cast<std::uint32_t>(pixel[2]) << 8U)
         | static_cast<std::uint32_t>(pixel[3]);
}

// Formats a 0xRRGGBBAA value as wx does; the alpha nibble pair is dropped when
// the comparison ignores alpha.
std::string FormatHex(std::uint32_t value, bool with_alpha)
{
    std::ostringstream out;
    out << "0x" << std::hex << std::setfill('0');
    if(with_alpha) {
        out << std::setw(8) << value;
    } else {
        out << std::setw(6) << (value >> 8U);
    }
    return out.str();
}

const std::uint8_t* PixelPointer(const Image& image, int pixel_x, int pixel_y)
{
    const std::size_t index = static_cast<std::size_t>(pixel_y) * static_cast<std::size_t>(image.width)
                            + static_cast<std::size_t>(pixel_x);
    return image.pixels.data() + (index * RGBA_CHANNELS);
}

// Worst checked-channel delta at a pixel; 0 when the images agree exactly.
int PixelDelta(const std::uint8_t* expected, const std::uint8_t* actual, std::size_t checked_channels)
{
    int worst = 0;
    for(std::size_t channel = 0; channel < checked_channels; ++channel) {
        const int higher = std::max(static_cast<int>(expected[channel]), static_cast<int>(actual[channel]));
        const int lower = std::min(static_cast<int>(expected[channel]), static_cast<int>(actual[channel]));
        worst = std::max(worst, higher - lower);
    }
    return worst;
}

std::size_t CheckedChannels(const CompareOptions& options)
{
    return options.check_alpha ? RGBA_CHANNELS : RGB_CHANNELS;
}

} // namespace

bool Image::IsValid() const
{
    if(width <= 0 || height <= 0) {
        return false;
    }
    const std::size_t expected_size = static_cast<std::size_t>(width) * static_cast<std::size_t>(height) * RGBA_CHANNELS;
    return pixels.size() == expected_size;
}

std::uint32_t Image::PixelAt(int pixel_x, int pixel_y) const
{
    return PackRgba(PixelPointer(*this, pixel_x, pixel_y));
}

CompareResult CompareImages(const Image& expected, const Image& actual, const CompareOptions& options)
{
    CompareResult result;
    result.options = options;
    result.expected_width = expected.width;
    result.expected_height = expected.height;
    result.actual_width = actual.width;
    result.actual_height = actual.height;

    if(!expected.IsValid() || !actual.IsValid()) {
        result.size_mismatch = true;
        return result;
    }

    if(expected.width != actual.width || expected.height != actual.height) {
        result.size_mismatch = true;
        return result;
    }

    const std::size_t checked_channels = CheckedChannels(options);
    const std::size_t total_pixels = static_cast<std::size_t>(expected.width) * static_cast<std::size_t>(expected.height);
    result.total_pixels = total_pixels;

    std::size_t differing_pixels = 0;
    int worst_delta = 0;

    for(int pixel_y = 0; pixel_y < expected.height; ++pixel_y) {
        for(int pixel_x = 0; pixel_x < expected.width; ++pixel_x) {
            const std::uint8_t* expected_pixel = PixelPointer(expected, pixel_x, pixel_y);
            const std::uint8_t* actual_pixel = PixelPointer(actual, pixel_x, pixel_y);
            const int delta = PixelDelta(expected_pixel, actual_pixel, checked_channels);
            if(delta <= options.tolerance) {
                continue;
            }

            ++differing_pixels;
            worst_delta = std::max(worst_delta, delta);
            if(!result.has_first_mismatch) {
                result.has_first_mismatch = true;
                result.first_mismatch.x = pixel_x;
                result.first_mismatch.y = pixel_y;
                result.first_mismatch.expected = PackRgba(expected_pixel);
                result.first_mismatch.actual = PackRgba(actual_pixel);
                result.first_mismatch.delta = delta;
            }
        }
    }

    result.differing_pixels = differing_pixels;
    result.differing_pixel_ratio = total_pixels == 0U
        ? 0.0
        : static_cast<double>(differing_pixels) / static_cast<double>(total_pixels);
    result.max_delta = worst_delta;

    const double allowed_pixels = options.max_differing_pixel_ratio * static_cast<double>(total_pixels);
    const bool ratio_ok = static_cast<double>(differing_pixels) <= (allowed_pixels + RATIO_EPSILON);
    const bool delta_ok = worst_delta <= options.max_delta;
    result.passed = ratio_ok && delta_ok;
    return result;
}

std::string CompareResult::Describe() const
{
    std::ostringstream out;
    if(size_mismatch) {
        out << "image sizes differ: expected " << expected_width << "x" << expected_height
            << ", actual " << actual_width << "x" << actual_height;
        return out.str();
    }

    out << std::setprecision(6);
    if(passed) {
        out << "images match within tolerance " << options.tolerance
            << " (" << differing_pixels << " of " << total_pixels << " pixels differ, max channel delta " << max_delta << ')';
        return out.str();
    }

    if(has_first_mismatch) {
        out << "first mismatch is at (" << first_mismatch.x << ", " << first_mismatch.y << ") which has value "
            << FormatHex(first_mismatch.actual, options.check_alpha) << " instead of the expected "
            << FormatHex(first_mismatch.expected, options.check_alpha) << "; ";
    }

    out << differing_pixels << " of " << total_pixels << " pixels differ (ratio " << differing_pixel_ratio
        << ", allowed " << options.max_differing_pixel_ratio << "), max channel delta " << max_delta
        << " (cap " << options.max_delta << "), tolerance " << options.tolerance;
    return out.str();
}

LoadResult LoadPng(const std::filesystem::path& path)
{
    LoadResult result;

    std::ifstream input(path, std::ios::binary);
    if(!input.is_open()) {
        result.error = "cannot open '" + path.string() + "'";
        return result;
    }

    const std::string raw((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    if(raw.empty()) {
        result.error = "empty file '" + path.string() + "'";
        return result;
    }
    const std::vector<std::uint8_t> bytes(raw.begin(), raw.end());

    int width = 0;
    int height = 0;
    int source_channels = 0;
    stbi_uc* decoded = stbi_load_from_memory(bytes.data(),
                                             static_cast<int>(bytes.size()),
                                             &width,
                                             &height,
                                             &source_channels,
                                             static_cast<int>(RGBA_CHANNELS));
    if(decoded == nullptr) {
        const char* reason = stbi_failure_reason();
        result.error = "cannot decode '" + path.string() + "': " + (reason == nullptr ? "unknown error" : reason);
        return result;
    }

    if(width <= 0 || height <= 0) {
        stbi_image_free(decoded);
        result.error = "decoded image has invalid dimensions: '" + path.string() + "'";
        return result;
    }

    Image image;
    image.width = width;
    image.height = height;
    const std::size_t pixel_count = static_cast<std::size_t>(width) * static_cast<std::size_t>(height) * RGBA_CHANNELS;
    image.pixels.assign(decoded, decoded + pixel_count);
    stbi_image_free(decoded);

    result.image = std::move(image);
    result.ok = true;
    return result;
}

FileCompareResult ComparePng(const std::filesystem::path& expected_path,
                             const std::filesystem::path& actual_path,
                             const CompareOptions& options,
                             const std::filesystem::path& diff_path)
{
    FileCompareResult result;

    const LoadResult expected = LoadPng(expected_path);
    if(!expected.ok) {
        result.error = "expected " + expected.error;
        return result;
    }

    const LoadResult actual = LoadPng(actual_path);
    if(!actual.ok) {
        result.error = "actual " + actual.error;
        return result;
    }

    result.ok = true;
    result.comparison = CompareImages(expected.image, actual.image, options);

    if(!result.comparison.passed && !diff_path.empty()) {
        std::string error;
        if(WriteDiffPng(diff_path, expected.image, actual.image, options, error)) {
            result.diff_written = true;
            result.diff_path = diff_path.string();
        } else {
            result.error = error;
        }
    }

    return result;
}

bool WriteDiffPng(const std::filesystem::path& output_path,
                  const Image& expected,
                  const Image& actual,
                  const CompareOptions& options,
                  std::string& error)
{
    if(!expected.IsValid() || !actual.IsValid() || expected.width != actual.width || expected.height != actual.height) {
        error = "cannot build a diff for invalid or differently sized images";
        return false;
    }

    const std::size_t checked_channels = CheckedChannels(options);
    const std::size_t total_pixels = static_cast<std::size_t>(expected.width) * static_cast<std::size_t>(expected.height);

    // Bitmap is ARGB32 premultiplied; every colour below is fully opaque, so
    // premultiplication is the identity and the bytes are simply B,G,R,A.
    std::vector<std::uint8_t> argb(total_pixels * RGBA_CHANNELS, 0U);
    for(std::size_t index = 0; index < total_pixels; ++index) {
        const std::uint8_t* expected_pixel = expected.pixels.data() + (index * RGBA_CHANNELS);
        const std::uint8_t* actual_pixel = actual.pixels.data() + (index * RGBA_CHANNELS);
        const int delta = PixelDelta(expected_pixel, actual_pixel, checked_channels);

        std::uint8_t red = 0U;
        std::uint8_t green = 0U;
        std::uint8_t blue = 0U;
        if(delta > options.tolerance) {
            red = 255U; // differing pixel: solid red
        } else {
            // Matching pixel: a dimmed luminance rendering of the expected image.
            const int luminance = ((299 * static_cast<int>(expected_pixel[0]))
                                 + (587 * static_cast<int>(expected_pixel[1]))
                                 + (114 * static_cast<int>(expected_pixel[2]))) / 1000;
            const std::uint8_t dimmed = static_cast<std::uint8_t>(luminance / 4);
            red = dimmed;
            green = dimmed;
            blue = dimmed;
        }

        argb[(index * RGBA_CHANNELS) + 0U] = blue;
        argb[(index * RGBA_CHANNELS) + 1U] = green;
        argb[(index * RGBA_CHANNELS) + 2U] = red;
        argb[(index * RGBA_CHANNELS) + 3U] = 255U;
    }

    const wxlunasvg::Bitmap bitmap(argb.data(), expected.width, expected.height, expected.width * static_cast<int>(RGBA_CHANNELS));
    if(!bitmap.writeToPng(output_path.string())) {
        error = "failed to write diff PNG '" + output_path.string() + "'";
        return false;
    }

    return true;
}

} // namespace test
} // namespace wxlunasvg
