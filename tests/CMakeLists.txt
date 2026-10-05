# wxlunasvg test suite - standalone, cross-platform, Catch2 v3 + CTest.
#
# Reached only when LUNASVG_BUILD_TESTS is ON *and* wxlunasvg is configured as the
# top-level project (see the root CMakeLists.txt). wxlunasvg is consumed by
# wxWidgets as a git submodule and compiled from an explicit source list, so wx's
# build must never see Catch2 or the test sources.
#
# Test-only dependencies are always obtained with FetchContent and never added as
# nested git submodules (plan decision 2b #14).

include(FetchContent)

# --- Catch2 v3 -------------------------------------------------------------
# The tag is pinned here; bump it deliberately. Catch2 v3 ships per-feature
# headers, so the tests include <catch2/catch_test_macros.hpp>. wxWidgets' harness
# ships Catch2 v2.13.10, where the same macros come from <catch2/catch.hpp>. The
# suite restricts itself to the common macro subset
# (TEST_CASE / CHECK / REQUIRE / REQUIRE_FALSE) so a Phase 7 port into the wx
# harness is a one-line include change.
set(WXLUNASVG_CATCH2_TAG "v3.7.1")

# Offline / pre-cloned override (plan section 8.2 #2): point this at an existing
# Catch2 v3 checkout to skip the network fetch entirely.
set(LUNASVG_CATCH2_DIR "" CACHE PATH "Pre-cloned Catch2 v3 source tree; skips the FetchContent download when set")

if(LUNASVG_CATCH2_DIR)
    message(STATUS "wxlunasvg tests: using local Catch2 from ${LUNASVG_CATCH2_DIR}")
    add_subdirectory("${LUNASVG_CATCH2_DIR}" "${CMAKE_CURRENT_BINARY_DIR}/catch2" EXCLUDE_FROM_ALL)
else()
    message(STATUS "wxlunasvg tests: fetching Catch2 ${WXLUNASVG_CATCH2_TAG}")
    FetchContent_Declare(Catch2
        GIT_REPOSITORY https://github.com/catchorg/Catch2.git
        GIT_TAG ${WXLUNASVG_CATCH2_TAG}
        GIT_SHALLOW TRUE
    )
    FetchContent_MakeAvailable(Catch2)
endif()

# --- golden-image comparison engine (Phase 3) ------------------------------
# Decodes PNGs with the vendored stb_image reader (decision 2b #8) and compares
# decoded pixels, mirroring wx's RGBSimilarTo / RGBASimilarTo semantics. Shared
# by the test binary and by the pngcompare / bless tooling.
add_library(wxlunasvg_test_support STATIC
    support/compare.cpp
)

target_include_directories(wxlunasvg_test_support PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/support
)

target_link_libraries(wxlunasvg_test_support PUBLIC lunasvg::lunasvg)
target_compile_features(wxlunasvg_test_support PUBLIC cxx_std_17)

# --- test binary -----------------------------------------------------------
add_executable(wxlunasvg_tests
    unit/api_smoke.cpp
    unit/structural.cpp
    unit/compare_engine.cpp
)

target_link_libraries(wxlunasvg_tests PRIVATE wxlunasvg_test_support lunasvg::lunasvg Catch2::Catch2WithMain)
target_compile_features(wxlunasvg_tests PRIVATE cxx_std_17)

# Absolute path to the wxlunasvg checkout; the structural tests read files from
# it (header guards, namespace invariants).
get_filename_component(WXLUNASVG_SOURCE_DIR "${CMAKE_CURRENT_SOURCE_DIR}/.." ABSOLUTE)
target_compile_definitions(wxlunasvg_tests PRIVATE
    WXLUNASVG_SOURCE_DIR="${WXLUNASVG_SOURCE_DIR}"
)

# ctest is the canonical runner; tests/run_tests.py is only a thin wrapper.
add_test(NAME wxlunasvg_tests COMMAND wxlunasvg_tests)

# --- svgrender helper ------------------------------------------------------
# Small standalone SVG -> PNG renderer used to produce before/after evidence and
# to render a case at a chosen size/background.
add_executable(svgrender tools/svgrender.cpp)
target_link_libraries(svgrender PRIVATE lunasvg::lunasvg)
target_compile_features(svgrender PRIVATE cxx_std_17)

# --- pngcompare helper -----------------------------------------------------
# Tolerance-based PNG comparison CLI: the Phase 3 replacement for the
# prototype's byte-exact `test_svg_png --compare` (plan sections 4 and 9). Used
# by tests/tools/bless.py and usable by hand to inspect a failing case.
add_executable(pngcompare tools/pngcompare.cpp)
target_link_libraries(pngcompare PRIVATE wxlunasvg_test_support)
target_compile_features(pngcompare PRIVATE cxx_std_17)

# --- golden-image corpus (Phase 4) -----------------------------------------
# The corpus runner is Python because the per-case options live in
# tests/data/manifest.json and the C++ engine deliberately has no JSON parser
# (plan Phase 3); ctest owns the scheduling and run_cases.py only renders,
# compares and interprets each case's expectedStatus. Python, not PowerShell
# (plan decision 2b #18). The W3C reference subset is report-only and is NOT
# registered here - it is `tests/tools/run_w3c.py` (plan decision 2b #13).
find_package(Python3 COMPONENTS Interpreter QUIET)
if(Python3_Interpreter_FOUND)
    add_test(NAME wxlunasvg_cases
        COMMAND ${Python3_EXECUTABLE}
                ${CMAKE_CURRENT_SOURCE_DIR}/tools/run_cases.py
                --build-dir ${CMAKE_BINARY_DIR}
                --svgrender $<TARGET_FILE:svgrender>
                --pngcompare $<TARGET_FILE:pngcompare>
    )
    set_tests_properties(wxlunasvg_cases PROPERTIES LABELS "corpus")
else()
    message(WARNING
        "Python3 interpreter not found: the golden-image corpus test "
        "(wxlunasvg_cases) will not be registered.")
endif()
