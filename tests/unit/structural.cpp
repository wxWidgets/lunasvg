/*
 * Structural / invariant tests for the wxlunasvg fork.
 *
 * These assert the guarantees the fork itself must hold once
 * scripts/post_merge.py has run, and they need no golden image data:
 *   - include/lunasvg.h keeps the C++17 #error guard and the wxWidgets defines
 *   - the public namespace is wxlunasvg and the legacy namespace declaration is
 *     gone from every C++ file in the checkout
 *
 * Catch2 include-path delta: <catch2/catch_test_macros.hpp> here (Catch2 v3) vs
 * <catch2/catch.hpp> in wxWidgets' Catch2 v2.13.10. Common macro subset only.
 */

#include <catch2/catch_test_macros.hpp>

#include <filesystem>
#include <fstream>
#include <iterator>
#include <string>
#include <system_error>
#include <vector>

#ifndef WXLUNASVG_SOURCE_DIR
#error "WXLUNASVG_SOURCE_DIR must be defined by tests/CMakeLists.txt"
#endif

static std::filesystem::path RepoRoot() {
  return std::filesystem::path(WXLUNASVG_SOURCE_DIR);
}

static std::filesystem::path HeaderPath() {
  return RepoRoot() / "include" / "lunasvg.h";
}

static std::string ReadTextFile(const std::filesystem::path &file_path) {
  std::ifstream input(file_path, std::ios::binary);
  if (!input.is_open()) {
    return std::string();
  }
  return std::string((std::istreambuf_iterator<char>(input)),
                     std::istreambuf_iterator<char>());
}

/*
 * Assembled at runtime so that scripts/post_merge.py - which rewrites the
 * legacy namespace declaration in every C++ file it touches - cannot rewrite
 * this probe string in the test source itself.
 */
static std::string LegacyNamespaceDeclaration() {
  return std::string("namespace ") + "lunasvg";
}

static bool IsCppSourceFile(const std::filesystem::path &file_path) {
  static const std::vector<std::string> extensions = {
      ".c", ".cc", ".cpp", ".cxx", ".h", ".hpp", ".hxx", ".ipp"};
  const std::string extension = file_path.extension().string();
  for (const std::string &candidate : extensions) {
    if (candidate == extension) {
      return true;
    }
  }
  return false;
}

/*
 * Skip VCS / agent directories and build trees so the scan stays fast, avoids
 * generated sources, and never walks a Catch2 checkout under build/.
 */
static bool IsPrunedDirectory(const std::filesystem::path &dir_path) {
  const std::string name = dir_path.filename().string();
  if (name.empty()) {
    return false;
  }
  if (name.front() == '.') {
    return true;
  }
  return name == "build" || name == "_deps" || name == "CMakeFiles" ||
         name == "Testing";
}

static std::vector<std::filesystem::path>
FindCppFilesContaining(const std::string &needle) {
  std::vector<std::filesystem::path> matches;
  const std::filesystem::recursive_directory_iterator end_iterator;
  std::error_code error;

  for (std::filesystem::recursive_directory_iterator iterator(
           RepoRoot(),
           std::filesystem::directory_options::skip_permission_denied, error);
       iterator != end_iterator; iterator.increment(error)) {
    if (error) {
      error.clear();
      continue;
    }

    const std::filesystem::directory_entry &entry = *iterator;
    if (entry.is_directory(error)) {
      error.clear();
      if (IsPrunedDirectory(entry.path())) {
        iterator.disable_recursion_pending();
      }
      continue;
    }

    if (!entry.is_regular_file(error)) {
      error.clear();
      continue;
    }

    if (!IsCppSourceFile(entry.path())) {
      continue;
    }

    if (ReadTextFile(entry.path()).find(needle) != std::string::npos) {
      matches.push_back(entry.path());
    }
  }

  return matches;
}

static std::string JoinPaths(const std::vector<std::filesystem::path> &paths) {
  std::string joined;
  for (const std::filesystem::path &path : paths) {
    if (!joined.empty()) {
      joined += '\n';
    }
    joined += path.string();
  }
  return joined;
}

TEST_CASE("WXLUNASVG_SOURCE_DIR points at the checkout", "[structural]") {
  CHECK(std::filesystem::is_regular_file(HeaderPath()));
  CHECK(std::filesystem::is_directory(RepoRoot() / "source"));
}

TEST_CASE("public header keeps the C++17 error guard", "[structural][header]") {
  const std::string header = ReadTextFile(HeaderPath());
  REQUIRE_FALSE(header.empty());
  CHECK(header.find("201703L") != std::string::npos);
  CHECK(header.find("#error") != std::string::npos);
  CHECK(header.find("C++17 or later is required") != std::string::npos);
}

TEST_CASE("public header keeps the wxWidgets defines block",
          "[structural][header]") {
  const std::string header = ReadTextFile(HeaderPath());
  REQUIRE_FALSE(header.empty());
  CHECK(header.find("WXBUILDING") != std::string::npos);
  CHECK(header.find("LUNASVG_BUILD_STATIC") != std::string::npos);
}

TEST_CASE("public header declares the wxlunasvg namespace",
          "[structural][namespace]") {
  const std::string header = ReadTextFile(HeaderPath());
  REQUIRE_FALSE(header.empty());
  CHECK(header.find("namespace wxlunasvg") != std::string::npos);
}

TEST_CASE("no C++ file keeps the legacy namespace declaration",
          "[structural][namespace]") {
  const std::string offenders =
      JoinPaths(FindCppFilesContaining(LegacyNamespaceDeclaration()));
  CHECK(offenders == std::string());
}
