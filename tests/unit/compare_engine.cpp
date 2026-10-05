/*
 * Golden-image comparison engine tests (plan Phase 3).
 *
 * Two layers:
 *   - CompareImages is exercised on synthetic in-memory images, which pins the
 *     wx-semantics down exactly (per-channel tolerance, alpha awareness, first
 *     mismatch reporting, max-delta cap, differing-pixel ratio);
 *   - ComparePng is exercised end-to-end on real PNGs rendered by liblunasvg,
 *     including the required "deliberately perturbed baseline fails with a
 *     useful diff" check.
 *
 * Catch2 include-path delta: <catch2/catch_test_macros.hpp> here (Catch2 v3) vs
 * <catch2/catch.hpp> in wxWidgets' Catch2 v2.13.10. Common macro subset only.
 */

#include <catch2/catch_test_macros.hpp>

#include "compare.h"

#include <lunasvg.h>

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <memory>
#include <string>
#include <system_error>
#include <vector>

namespace {

constexpr std::size_t RGBA_CHANNELS = 4U;

std::filesystem::path TempPath(const std::string& file_name)
{
    return std::filesystem::temp_directory_path() / file_name;
}

void RemoveQuietly(const std::filesystem::path& file_path)
{
    std::error_code ignored;
    std::filesystem::remove(file_path, ignored);
}

wxlunasvg::test::Image SolidImage(int width, int height, std::uint8_t red, std::uint8_t green, std::uint8_t blue, std::uint8_t alpha)
{
    wxlunasvg::test::Image image;
    image.width = width;
    image.height = height;
    const std::size_t pixel_count = static_cast<std::size_t>(width) * static_cast<std::size_t>(height);
    image.pixels.resize(pixel_count * RGBA_CHANNELS);
    for(std::size_t index = 0; index < pixel_count; ++index) {
        image.pixels[(index * RGBA_CHANNELS) + 0U] = red;
        image.pixels[(index * RGBA_CHANNELS) + 1U] = green;
        image.pixels[(index * RGBA_CHANNELS) + 2U] = blue;
        image.pixels[(index * RGBA_CHANNELS) + 3U] = alpha;
    }
    return image;
}

void SetPixel(wxlunasvg::test::Image& image,
              int pixel_x,
              int pixel_y,
              std::uint8_t red,
              std::uint8_t green,
              std::uint8_t blue,
              std::uint8_t alpha)
{
    const std::size_t index = (static_cast<std::size_t>(pixel_y) * static_cast<std::size_t>(image.width))
                            + static_cast<std::size_t>(pixel_x);
    image.pixels[(index * RGBA_CHANNELS) + 0U] = red;
    image.pixels[(index * RGBA_CHANNELS) + 1U] = green;
    image.pixels[(index * RGBA_CHANNELS) + 2U] = blue;
    image.pixels[(index * RGBA_CHANNELS) + 3U] = alpha;
}

// Renders an inline SVG to a PNG file through the public library API.
std::filesystem::path RenderPng(const std::string& svg,
                                const std::string& file_name,
                                int width,
                                int height,
                                std::uint32_t background)
{
    const std::unique_ptr<wxlunasvg::Document> document = wxlunasvg::Document::loadFromData(svg);
    REQUIRE(document != nullptr);
    const wxlunasvg::Bitmap bitmap = document->renderToBitmap(width, height, background);
    REQUIRE_FALSE(bitmap.isNull());

    const std::filesystem::path png_path = TempPath(file_name);
    REQUIRE(bitmap.writeToPng(png_path.string()));
    return png_path;
}

// 4x4 SVG whose only content is a single opaque red pixel at (0,0).
std::string OnePixelSvg(const std::string& red_fill)
{
    return "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"4\" height=\"4\">"
           "<rect x=\"0\" y=\"0\" width=\"1\" height=\"1\" fill=\"" + red_fill + "\"/>"
           "</svg>";
}

} // namespace

TEST_CASE("CompareImages matches identical images exactly", "[compare][engine]")
{
    const wxlunasvg::test::Image image = SolidImage(4, 4, 10U, 20U, 30U, 255U);
    const wxlunasvg::test::CompareOptions options;

    const wxlunasvg::test::CompareResult result = wxlunasvg::test::CompareImages(image, image, options);

    CHECK(result.passed);
    CHECK_FALSE(result.size_mismatch);
    CHECK(result.total_pixels == 16U);
    CHECK(result.differing_pixels == 0U);
    CHECK(result.differing_pixel_ratio == 0.0);
    CHECK(result.max_delta == 0);
    CHECK_FALSE(result.has_first_mismatch);
    CHECK(result.Describe().find("images match") != std::string::npos);
}

TEST_CASE("CompareImages honours the per-channel tolerance", "[compare][engine]")
{
    const wxlunasvg::test::Image expected = SolidImage(4, 4, 10U, 20U, 30U, 255U);
    wxlunasvg::test::Image actual = expected;
    SetPixel(actual, 2, 1, 13U, 20U, 30U, 255U); // +3 on red

    wxlunasvg::test::CompareOptions options;

    options.tolerance = 2;
    const wxlunasvg::test::CompareResult strict = wxlunasvg::test::CompareImages(expected, actual, options);
    CHECK_FALSE(strict.passed);
    CHECK(strict.differing_pixels == 1U);
    CHECK(strict.max_delta == 3);

    options.tolerance = 3;
    const wxlunasvg::test::CompareResult forgiving = wxlunasvg::test::CompareImages(expected, actual, options);
    CHECK(forgiving.passed);
    CHECK(forgiving.differing_pixels == 0U);
    CHECK(forgiving.max_delta == 0);
}

TEST_CASE("CompareImages reports the first mismatching pixel like wx", "[compare][engine]")
{
    const wxlunasvg::test::Image expected = SolidImage(4, 4, 0x11U, 0x22U, 0x33U, 0xFFU);
    wxlunasvg::test::Image actual = expected;
    SetPixel(actual, 2, 1, 0x11U, 0x22U, 0x34U, 0xFFU);

    const wxlunasvg::test::CompareOptions options;
    const wxlunasvg::test::CompareResult result = wxlunasvg::test::CompareImages(expected, actual, options);

    REQUIRE(result.has_first_mismatch);
    CHECK(result.first_mismatch.x == 2);
    CHECK(result.first_mismatch.y == 1);
    CHECK(result.first_mismatch.expected == 0x112233FFU);
    CHECK(result.first_mismatch.actual == 0x112234FFU);
    CHECK(result.first_mismatch.delta == 1);

    const std::string description = result.Describe();
    CHECK(description.find("first mismatch is at (2, 1)") != std::string::npos);
    CHECK(description.find("0x112234ff") != std::string::npos);
    CHECK(description.find("instead of the expected 0x112233ff") != std::string::npos);
}

TEST_CASE("CompareImages is alpha-aware", "[compare][engine]")
{
    const wxlunasvg::test::Image expected = SolidImage(4, 4, 40U, 50U, 60U, 200U);
    wxlunasvg::test::Image actual = expected;
    SetPixel(actual, 0, 3, 40U, 50U, 60U, 207U); // +7 on alpha only

    wxlunasvg::test::CompareOptions options;
    options.check_alpha = true;
    const wxlunasvg::test::CompareResult rgba = wxlunasvg::test::CompareImages(expected, actual, options);
    CHECK_FALSE(rgba.passed);
    CHECK(rgba.differing_pixels == 1U);

    options.check_alpha = false;
    const wxlunasvg::test::CompareResult rgb = wxlunasvg::test::CompareImages(expected, actual, options);
    CHECK(rgb.passed);
    CHECK(rgb.differing_pixels == 0U);
}

TEST_CASE("CompareImages enforces the max-delta cap", "[compare][engine]")
{
    const wxlunasvg::test::Image expected = SolidImage(4, 4, 0U, 0U, 0U, 255U);
    wxlunasvg::test::Image actual = expected;
    SetPixel(actual, 1, 1, 40U, 0U, 0U, 255U); // +40 on red

    wxlunasvg::test::CompareOptions options;
    options.max_differing_pixel_ratio = 1.0; // every pixel may differ

    options.max_delta = 255;
    const wxlunasvg::test::CompareResult capped_loosely = wxlunasvg::test::CompareImages(expected, actual, options);
    CHECK(capped_loosely.passed);
    CHECK(capped_loosely.max_delta == 40);

    options.max_delta = 10;
    const wxlunasvg::test::CompareResult capped_tightly = wxlunasvg::test::CompareImages(expected, actual, options);
    CHECK_FALSE(capped_tightly.passed);
}

TEST_CASE("CompareImages enforces the differing-pixel ratio", "[compare][engine]")
{
    const wxlunasvg::test::Image expected = SolidImage(4, 4, 0U, 0U, 0U, 255U);
    wxlunasvg::test::Image actual = expected;
    SetPixel(actual, 0, 0, 5U, 0U, 0U, 255U);
    SetPixel(actual, 1, 0, 5U, 0U, 0U, 255U);
    SetPixel(actual, 2, 0, 5U, 0U, 0U, 255U); // 3 of 16 pixels differ

    wxlunasvg::test::CompareOptions options;
    options.tolerance = 0;

    options.max_differing_pixel_ratio = 0.1; // 0.1 * 16 = 1.6 < 3
    const wxlunasvg::test::CompareResult tight = wxlunasvg::test::CompareImages(expected, actual, options);
    CHECK_FALSE(tight.passed);
    CHECK(tight.differing_pixels == 3U);

    options.max_differing_pixel_ratio = 0.2; // 0.2 * 16 = 3.2 >= 3
    const wxlunasvg::test::CompareResult loose = wxlunasvg::test::CompareImages(expected, actual, options);
    CHECK(loose.passed);
    CHECK(loose.differing_pixels == 3U);
}

TEST_CASE("CompareImages reports a size mismatch", "[compare][engine]")
{
    const wxlunasvg::test::Image expected = SolidImage(4, 4, 0U, 0U, 0U, 255U);
    const wxlunasvg::test::Image actual = SolidImage(5, 4, 0U, 0U, 0U, 255U);

    const wxlunasvg::test::CompareOptions options;
    const wxlunasvg::test::CompareResult result = wxlunasvg::test::CompareImages(expected, actual, options);

    CHECK_FALSE(result.passed);
    CHECK(result.size_mismatch);
    CHECK(result.Describe().find("image sizes differ: expected 4x4, actual 5x4") != std::string::npos);
}

TEST_CASE("ComparePng matches identical renders", "[compare][png]")
{
    const std::filesystem::path first = RenderPng(OnePixelSvg("#ff0000"), "wxlunasvg_compare_first.png", 4, 4, 0x00000000U);
    const std::filesystem::path second = RenderPng(OnePixelSvg("#ff0000"), "wxlunasvg_compare_second.png", 4, 4, 0x00000000U);

    const wxlunasvg::test::CompareOptions options;
    const wxlunasvg::test::FileCompareResult compare = wxlunasvg::test::ComparePng(first, second, options);

    REQUIRE(compare.ok);
    CHECK(compare.comparison.passed);
    CHECK_FALSE(compare.diff_written);

    RemoveQuietly(first);
    RemoveQuietly(second);
}

TEST_CASE("a deliberately perturbed baseline fails with a useful diff", "[compare][png]")
{
    const std::filesystem::path baseline = RenderPng(OnePixelSvg("#ff0000"), "wxlunasvg_compare_baseline.png", 4, 4, 0x00000000U);
    const std::filesystem::path current = RenderPng(OnePixelSvg("#ff0003"), "wxlunasvg_compare_current.png", 4, 4, 0x00000000U);
    const std::filesystem::path diff_path = TempPath("wxlunasvg_compare_diff.png");
    RemoveQuietly(diff_path);

    wxlunasvg::test::CompareOptions options;
    const wxlunasvg::test::FileCompareResult compare =
        wxlunasvg::test::ComparePng(baseline, current, options, diff_path);

    REQUIRE(compare.ok);
    CHECK_FALSE(compare.comparison.passed);
    CHECK(compare.comparison.differing_pixels == 1U);
    CHECK(compare.comparison.total_pixels == 16U);
    CHECK(compare.comparison.first_mismatch.x == 0);
    CHECK(compare.comparison.first_mismatch.y == 0);
    CHECK(compare.comparison.first_mismatch.delta == 3);
    CHECK(compare.comparison.Describe().find("first mismatch is at (0, 0)") != std::string::npos);

    REQUIRE(compare.diff_written);
    CHECK(std::filesystem::is_regular_file(diff_path));

    const wxlunasvg::test::LoadResult diff = wxlunasvg::test::LoadPng(diff_path);
    REQUIRE(diff.ok);
    CHECK(diff.image.width == 4);
    CHECK(diff.image.height == 4);

    // Same perturbation, but a tolerance of 3 (or a permissive ratio) accepts it.
    wxlunasvg::test::CompareOptions tolerant;
    tolerant.tolerance = 3;
    const wxlunasvg::test::FileCompareResult tolerated = wxlunasvg::test::ComparePng(baseline, current, tolerant);
    REQUIRE(tolerated.ok);
    CHECK(tolerated.comparison.passed);

    wxlunasvg::test::CompareOptions ratio_options;
    ratio_options.max_differing_pixel_ratio = 0.1; // 1/16 = 0.0625 <= 0.1
    const wxlunasvg::test::FileCompareResult tolerated_ratio = wxlunasvg::test::ComparePng(baseline, current, ratio_options);
    REQUIRE(tolerated_ratio.ok);
    CHECK(tolerated_ratio.comparison.passed);

    RemoveQuietly(baseline);
    RemoveQuietly(current);
    RemoveQuietly(diff_path);
}

TEST_CASE("LoadPng fails gracefully on a non-PNG file", "[compare][png]")
{
    const std::filesystem::path bogus = TempPath("wxlunasvg_compare_bogus.png");
    {
        std::ofstream output(bogus, std::ios::binary | std::ios::trunc);
        REQUIRE(output.is_open());
        output << "this is not a PNG";
    }

    const wxlunasvg::test::LoadResult result = wxlunasvg::test::LoadPng(bogus);
    CHECK_FALSE(result.ok);
    CHECK_FALSE(result.error.empty());

    RemoveQuietly(bogus);
}
