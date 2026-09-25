/*
 * pngcompare - tolerance-based PNG comparison CLI for the wxlunasvg test suite.
 *
 * Usage:
 *   pngcompare <expected.png> <actual.png> [options]
 *
 * Options:
 *   --tolerance N     per-channel tolerance (default 0, exact-but-for-alpha)
 *   --max-delta N     hard cap on the worst differing-channel delta (default 255)
 *   --max-ratio F     largest tolerated fraction of differing pixels (default 0)
 *   --no-alpha        compare RGB only (wx RGBSimilarTo) instead of RGBA
 *   --diff-out PATH   write a diff PNG when the comparison fails
 *   --quiet           suppress the summary when the images match
 *   --help            show this message
 *
 * Exit codes (the prototype's shape, plan section 4):
 *   0  images match
 *   1  invalid arguments
 *   2  an input could not be loaded or decoded
 *   4  images differ
 *
 * This is the tolerance-based replacement for the prototype's byte-exact
 * `test_svg_png --compare` (plan sections 4 and 9).
 */

#include "compare.h"

#include <cstddef>
#include <exception>
#include <iostream>
#include <string>
#include <vector>

static constexpr int PROGRAM_SUCCESS = 0;
static constexpr int PROGRAM_USAGE = 1;
static constexpr int PROGRAM_LOAD_FAILED = 2;
static constexpr int PROGRAM_COMPARISON_FAILED = 4;

static void PrintUsage()
{
    std::cout << "Usage: pngcompare <expected.png> <actual.png> [options]\n"
                 "Options:\n"
                 "   --tolerance N     per-channel tolerance (default 0)\n"
                 "   --max-delta N     cap on the worst differing-channel delta (default 255)\n"
                 "   --max-ratio F     tolerated fraction of differing pixels (default 0)\n"
                 "   --no-alpha        compare RGB only (RGBSimilarTo) instead of RGBA\n"
                 "   --diff-out PATH   write a diff PNG when the comparison fails\n"
                 "   --quiet           suppress the summary on success\n"
                 "   --help            show this message\n";
}

static bool ParseInt(const std::string& text, int& value)
{
    try {
        std::size_t consumed = 0;
        const int parsed = std::stoi(text, &consumed);
        if(consumed != text.size()) {
            return false;
        }
        value = parsed;
    } catch(const std::exception&) {
        return false;
    }
    return true;
}

static bool ParseDouble(const std::string& text, double& value)
{
    try {
        std::size_t consumed = 0;
        const double parsed = std::stod(text, &consumed);
        if(consumed != text.size()) {
            return false;
        }
        value = parsed;
    } catch(const std::exception&) {
        return false;
    }
    return true;
}

int main(int argc, char* argv[])
{
    std::vector<std::string> arguments;
    for(int index = 1; index < argc; ++index) {
        arguments.emplace_back(argv[index]);
    }

    for(const std::string& argument : arguments) {
        if(argument == "--help" || argument == "-h") {
            PrintUsage();
            return PROGRAM_SUCCESS;
        }
    }

    std::vector<std::string> positional;
    wxlunasvg::test::CompareOptions options;
    std::string diff_out;
    bool quiet = false;

    for(std::size_t index = 0; index < arguments.size(); ++index) {
        const std::string& argument = arguments[index];
        if(argument == "--no-alpha") {
            options.check_alpha = false;
            continue;
        }
        if(argument == "--quiet") {
            quiet = true;
            continue;
        }
        if(argument == "--tolerance" || argument == "--max-delta" || argument == "--max-ratio" || argument == "--diff-out") {
            if((index + 1U) >= arguments.size()) {
                std::cerr << "error: " << argument << " requires a value\n";
                return PROGRAM_USAGE;
            }
            const std::string value = arguments[index + 1U];
            ++index;

            if(argument == "--diff-out") {
                diff_out = value;
                continue;
            }
            if(argument == "--tolerance" && !ParseInt(value, options.tolerance)) {
                std::cerr << "error: invalid tolerance '" << value << "'\n";
                return PROGRAM_USAGE;
            }
            if(argument == "--max-delta" && !ParseInt(value, options.max_delta)) {
                std::cerr << "error: invalid max-delta '" << value << "'\n";
                return PROGRAM_USAGE;
            }
            if(argument == "--max-ratio" && !ParseDouble(value, options.max_differing_pixel_ratio)) {
                std::cerr << "error: invalid max-ratio '" << value << "'\n";
                return PROGRAM_USAGE;
            }
            continue;
        }
        if(!argument.empty() && argument.front() == '-') {
            std::cerr << "error: unknown option '" << argument << "'\n";
            PrintUsage();
            return PROGRAM_USAGE;
        }
        positional.push_back(argument);
    }

    if(positional.size() != 2U) {
        PrintUsage();
        return PROGRAM_USAGE;
    }

    const wxlunasvg::test::FileCompareResult compare =
        wxlunasvg::test::ComparePng(positional[0], positional[1], options, diff_out);

    if(!compare.ok) {
        std::cerr << "error: " << compare.error << '\n';
        return PROGRAM_LOAD_FAILED;
    }

    const wxlunasvg::test::CompareResult& result = compare.comparison;
    if(result.passed) {
        if(!quiet) {
            std::cout << result.Describe() << '\n';
        }
        return PROGRAM_SUCCESS;
    }

    std::cerr << result.Describe() << '\n';
    if(compare.diff_written) {
        std::cerr << "diff PNG written to " << compare.diff_path << '\n';
    }
    return PROGRAM_COMPARISON_FAILED;
}
