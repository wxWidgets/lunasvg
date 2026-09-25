/*
 * Public-API smoke tests for wxlunasvg.
 *
 * These exercise only the documented public surface of <lunasvg.h> and need no
 * golden image data, so they run on every platform independently of the
 * comparison engine added in Phase 3.
 *
 * Catch2 include-path delta: this file uses the Catch2 v3 header
 * <catch2/catch_test_macros.hpp>; wxWidgets' harness ships Catch2 v2.13.10 where
 * the same macros come from <catch2/catch.hpp>. Only the common macro subset
 * (TEST_CASE / CHECK / REQUIRE / REQUIRE_FALSE) is used so a Phase 7 port is a
 * one-line include change.
 */

#include <catch2/catch_approx.hpp>
#include <catch2/catch_test_macros.hpp>

#include <lunasvg.h>

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <memory>
#include <string>

static constexpr const char* SIMPLE_SVG =
    "<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"8\" height=\"8\">"
    "<rect x=\"4\" y=\"4\" width=\"4\" height=\"4\" fill=\"#ff0000\"/>"
    "</svg>";

/*
 * Colours are given as 0xRRGGBBAA. An opaque colour is unchanged by
 * premultiplication, so the stored ARGB32_Premultiplied pixel reads back as
 * 0xAARRGGBB.
 */
static constexpr std::uint32_t OPAQUE_BACKGROUND = 0x112233FFU;
static constexpr std::uint32_t OPAQUE_BACKGROUND_ARGB = 0xFF112233U;
static constexpr std::uint32_t OPAQUE_RED_ARGB = 0xFFFF0000U;

static std::uint32_t ReadPixel(const wxlunasvg::Bitmap& bitmap, int pixel_x, int pixel_y)
{
    const std::uint8_t* row_start = bitmap.data() + (static_cast<std::size_t>(pixel_y) * static_cast<std::size_t>(bitmap.stride()));
    const std::uint8_t* pixel_start = row_start + (static_cast<std::size_t>(pixel_x) * sizeof(std::uint32_t));
    std::uint32_t value = 0;
    std::memcpy(&value, pixel_start, sizeof(value));
    return value;
}

static std::filesystem::path TempFile(const std::string& filename)
{
    return std::filesystem::temp_directory_path() / filename;
}

static void RemoveQuietly(const std::filesystem::path& file_path)
{
    std::error_code ignored;
    std::filesystem::remove(file_path, ignored);
}

TEST_CASE("Document::loadFromData parses inline SVG", "[api][document]")
{
    const std::unique_ptr<wxlunasvg::Document> from_string = wxlunasvg::Document::loadFromData(std::string(SIMPLE_SVG));
    REQUIRE(from_string != nullptr);
    CHECK(from_string->width() == Catch::Approx(8.0F));
    CHECK(from_string->height() == Catch::Approx(8.0F));

    const std::unique_ptr<wxlunasvg::Document> from_c_string = wxlunasvg::Document::loadFromData(SIMPLE_SVG);
    REQUIRE(from_c_string != nullptr);
    CHECK(from_c_string->width() == Catch::Approx(8.0F));
}

TEST_CASE("Document::loadFromFile reads an SVG file from disk", "[api][document]")
{
    const std::filesystem::path svg_path = TempFile("wxlunasvg_api_smoke_input.svg");
    {
        std::ofstream output(svg_path, std::ios::binary | std::ios::trunc);
        REQUIRE(output.is_open());
        output << SIMPLE_SVG;
    }

    const std::unique_ptr<wxlunasvg::Document> document = wxlunasvg::Document::loadFromFile(svg_path.string());
    REQUIRE(document != nullptr);
    CHECK(document->width() == Catch::Approx(8.0F));
    CHECK(document->height() == Catch::Approx(8.0F));

    RemoveQuietly(svg_path);
}

TEST_CASE("Document::loadFromFile returns null for a missing file", "[api][document]")
{
    const std::unique_ptr<wxlunasvg::Document> document = wxlunasvg::Document::loadFromFile(TempFile("wxlunasvg-does-not-exist.svg").string());
    CHECK(document == nullptr);
}

TEST_CASE("renderToBitmap honours the requested size and background colour", "[api][render]")
{
    const std::unique_ptr<wxlunasvg::Document> document = wxlunasvg::Document::loadFromData(std::string(SIMPLE_SVG));
    REQUIRE(document != nullptr);

    const wxlunasvg::Bitmap bitmap = document->renderToBitmap(8, 8, OPAQUE_BACKGROUND);
    REQUIRE_FALSE(bitmap.isNull());
    CHECK(bitmap.width() == 8);
    CHECK(bitmap.height() == 8);
    CHECK(bitmap.stride() >= (8 * static_cast<int>(sizeof(std::uint32_t))));

    // (0,0) lies outside the 4x4 red rectangle, so it keeps the background.
    CHECK(ReadPixel(bitmap, 0, 0) == OPAQUE_BACKGROUND_ARGB);
    // (6,6) is inside the opaque red rectangle.
    CHECK(ReadPixel(bitmap, 6, 6) == OPAQUE_RED_ARGB);
}

TEST_CASE("Bitmap::writeToPng writes a PNG file", "[api][png]")
{
    const std::unique_ptr<wxlunasvg::Document> document = wxlunasvg::Document::loadFromData(std::string(SIMPLE_SVG));
    REQUIRE(document != nullptr);

    const wxlunasvg::Bitmap bitmap = document->renderToBitmap(8, 8, OPAQUE_BACKGROUND);
    REQUIRE_FALSE(bitmap.isNull());

    const std::filesystem::path png_path = TempFile("wxlunasvg_api_smoke_output.png");
    REQUIRE(bitmap.writeToPng(png_path.string()));
    REQUIRE(std::filesystem::is_regular_file(png_path));

    std::ifstream input(png_path, std::ios::binary);
    REQUIRE(input.is_open());
    const std::string bytes((std::istreambuf_iterator<char>(input)), std::istreambuf_iterator<char>());
    REQUIRE(bytes.size() > 8);

    // PNG signature: 89 50 4E 47 0D 0A 1A 0A
    CHECK(static_cast<unsigned char>(bytes[0]) == 0x89U);
    CHECK(bytes.compare(1, 3, "PNG") == 0);

    RemoveQuietly(png_path);
}

TEST_CASE("the public version API agrees with the header macros", "[api][version]")
{
    CHECK(lunasvg_version() == LUNASVG_VERSION);
    CHECK(std::string(lunasvg_version_string()) == std::string(LUNASVG_VERSION_STRING));
}
