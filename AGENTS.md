# AGENTS.md

This repository contains a C++17 logic network library (mockturtle) and a demo application (fullvision_demo).

## Build Commands

### Mockturtle (C++ logic network library)
```bash
cd mockturtle
mkdir build && cd build
cmake -DCMAKE_CXX_COMPILER=g++-13 -DMOCKTURTLE_BUILD_TESTS=ON ..
make run_tests
./test/run_tests
```

### Fullvision Demo
```bash
cd fullvision_demo
mkdir build && cd build
cmake ..
make
```

### Building everything (examples, tests, experiments)
```bash
cmake -DMOCKTURTLE_BUILD_EXAMPLES=ON -DMOCKTURTLE_BUILD_EXPERIMENTS=ON -DMOCKTURTLE_BUILD_TESTS=ON ..
make
```

## Running Tests

### Run all tests
```bash
./test/run_tests
```

### Run a single test by name/tag
```bash
./test/run_tests "[test_tag]"
./test/run_tests "test_case_name"
./test/run_tests "[serialize]"  # Run all tests tagged with [serialize]
```

### Running tests with sanitizers
```bash
cmake -DCMAKE_CXX_COMPILER=clang++-13 -DMOCKTURTLE_ENABLE_ASAN=ON -DMOCKTURTLE_BUILD_TESTS=ON ..
make run_tests
./test/run_tests
```

## Code Style Guidelines

### Formatting (clang-format)
Always run `clang-format -i <files>` before committing changes.
Key formatting rules:
- 2 spaces indentation (never tabs)
- No column limit
- Pointer alignment: Left (`int* ptr`)
- Brace wrapping: Custom (breaks after class, function, namespace, control statements, else, catch)
- Empty line before access modifiers only at logical block boundaries
- Include sorting: case-sensitive
- `#pragma once` for header guards

### File Headers
All source files must include the MIT license header at the top:
```cpp
/* mockturtle: C++ logic network library
 * Copyright (C) 2018-2022  EPFL
 *
 * Permission is hereby granted, free of charge, to any person
 * obtaining a copy of this software and associated documentation
 * files (the "Software"), to deal in the Software without
 * restriction, including limitation...
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND...
 */
```

### Documentation Comments
Use doxygen-style comments for files, classes, and functions:
```cpp
/*!
  \file filename.hpp
  \brief Brief description

  \author Name
*/
```

### Naming Conventions
- Namespaces: `lowercase` (e.g., `mockturtle`, `detail`)
- Classes/Structs: `PascalCase` (e.g., `SuperLib`, `SupergateSpec`)
- Functions: `snake_case` (e.g., `write_aiger`, `temp_directory`)
- Variables: `snake_case` (e.g., `num_gates`, `file_name`)
- Private members: `snake_case_` (e.g., `lib_`)
- Type aliases: `snake_case_t` or just `snake_case` (e.g., `node`, `signal`)
- Template parameters: Single uppercase letters (`T`, `Ntk`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `MAX_SIZE`)

### Imports and Includes
- Use `#pragma once` for header guards
- Standard library headers: `<algorithm>`, `<vector>`, etc.
- Project headers: `"../traits.hpp"` or `"mockturtle/networks/aig.hpp"`
- External library headers: `<fmt/format.h>`, `<lorina/aiger.hpp>`
- Include order: standard library headers first, then external, then project
- No `using namespace` directives in headers (except `using namespace mockturtle;` is okay in .cpp files)

### Types and Templates
- Use `auto` sparingly; prefer explicit types for function parameters and returns
- Template type parameters: `template<typename Ntk>` not `template<class Ntk>`
- Template template parameters: `template<typename Ntk, typename View>`
- Use `static_assert` with `is_network_type_v<Ntk>` for template constraints
- Use concepts if available (C++20): `requires is_network_type_v<Ntk>`

### Error Handling
- Use `assert()` for internal invariants and preconditions
- Use exceptions for recoverable errors (e.g., `std::runtime_error`)
- Return error codes from external library calls (e.g., `lorina::return_code::success`)
- Check return values and handle errors appropriately

### Linting
Pre-commit hooks check for:
- Trailing whitespace (except in lib/ directory)
- End-of-file newlines (except in lib/ directory)
- Typos (except in lib/, experiments/, docs/, .github/, .ql/)

Run pre-commit checks manually:
```bash
pre-commit run --all-files
```

### Testing with Catch2
- Define test cases: `TEST_CASE( "Test description", "[tag]" )`
- Use `CHECK` for non-fatal assertions, `REQUIRE` for fatal assertions
- Use `SECTION` for test cases with multiple scenarios
- Add unit tests for new functionality in `test/` folder
- Run tests to verify changes before submitting PRs

### Commit Guidelines
- Ensure all code follows project style (run `clang-format -i <files>`)
- Add unit tests for new features
- Add documentation (code comments and docs/ .rst files)
- Remove debugging code and editor-generated files
- Update changelog in `docs/changelog.rst` after PR submission

### Libraries Used
- `fmt` - string formatting
- `lorina` - file parsing (AIGER, BLIF, etc.)
- `kitty` - truth table operations
- `percy` - logic synthesis
- `json` - JSON (nlohmann/json, header-only)
- `rang` - terminal colors
- `parallel_hashmap` - parallel hash maps
