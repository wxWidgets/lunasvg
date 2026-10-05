# Runner image for running .github/workflows/tests.yml locally with nektos/act.
#
# act's default Ubuntu image (catthehacker/ubuntu:act-latest, currently Ubuntu
# 24.04 - the same base as the GitHub `ubuntu-latest` runner) already ships
# gcc/g++, make, python3, git and node, but it has neither CMake nor Clang. The
# suite needs both: CMake to configure/build (LUNASVG_BUILD_TESTS=ON) and Clang
# for the `clang` matrix legs and the ASAN+UBSAN job.
#
# This thin layer adds exactly those, so `.github/workflows/tests.yml` runs
# unchanged. It is deliberately tiny (~150 MB on top of the base image) instead
# of the catthehacker "full" image (~19 GB), which would otherwise be the
# CI-faithful choice.
#
# The VS Code task "act: tests.yml" builds this on demand; to build it by hand:
#   docker build -t wxlunasvg-act-tests:latest .github/act
FROM catthehacker/ubuntu:act-latest

# libclang-rt-dev supplies Clang's compiler-rt sanitizer runtimes
# (libclang_rt.asan*, libclang_rt.ubsan*), which the ASAN+UBSAN job needs to
# link. --no-install-recommends skips it otherwise, hence the explicit entry.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
        cmake \
        clang \
        libclang-rt-dev \
        ninja-build \
 && rm -rf /var/lib/apt/lists/*
