## 3.15.0

**Released on:** Unreleased

### Language

Dart 3.15 allows [`this` to be type promoted][this-promotion-issue], just like
a local variable, and [preserves more type promotions][#4757] at control flow
join points. To use these features, set your package's
[SDK constraint][language version] lower bound to 3.15 or greater
(`sdk: '^3.15.0'`).


## 3.14.0

**Released on:** Unreleased

### Libraries

#### `dart:ffi`

- Added `NativeFinalizer.callback`, which returns the finalization callback the
  finalizer was created with.
  For more details, see SDK issue [#63811][]
- Added `Abi.iosArm64e` and `Abi.macosArm64e` for the `arm64e` architecture

## 3.13.3

**Released on:** 2026-09-01

This is a patch release that:

- Fixes an issue where Windows to Linux cross compilation
  produced incorrect executables if the applicatios used
  build hooks to link native code. (issue [#63953][])

[#63953]: https://github.com/dart-lang/sdk/issues/63953

## 3.13.2

**Released on:** 2026-08-25

This is a patch release that:

- Fixes incorrect dart2wasm compilation of constructor invocations when
  the class was determined to be not allocatable. (issue [#63809][])
- Deprecates the legacy analyzer plugin system. (issue [#62164][])
- Fixes dart2js compiler crash when compiling code with
  nested constants in `record_use`. (issue [#64070][])
- Fixes a `dart format` crash and incorrect formatting with
  enums that use primary constructors.
  (issues [dart-lang/dart_style#1885][], [dart-lang/dart_style#1888][])

[#63809]: https://github.com/dart-lang/sdk/issues/63809
[#62164]: https://github.com/dart-lang/sdk/issues/62164
[#64070]: https://github.com/dart-lang/sdk/issues/64070

[dart-lang/dart_style#1885]: https://github.com/dart-lang/dart_style/issues/1885
[dart-lang/dart_style#1888]: https://github.com/dart-lang/dart_style/issues/1888


## 3.13.1

**Released on:** 2026-08-18

This is a patch release that:

- Fixes `dart fix --apply --code=migrate_design_widgets` to
  replace URIs in both import and export statements. (issue [#63968][])
- Fixes dart2wasm compiler crash in no-such-method forwarders.
  (issue [#63904][])
- Fixes dart2wasm compilation error if 3rd party `Type` implementations exist.
  (issue [#63843][])
- Fixes dart2wasm compiler crash if dynamic getter calls are used that
  target a getter implementation that was inferred to never return.
- Fixes dart2wasm compiler crash if named parameters in hierarchy have
  mixed "required"-ness. (issue [#60583][])
- Fixes `closure.hashCode` sometimes returning `null`. (issue [#64035][])

[#63968]: https://github.com/dart-lang/sdk/issues/63968
[#63904]: https://github.com/dart-lang/sdk/issues/63904
[#63843]: https://github.com/dart-lang/sdk/issues/63843
[#60583]: https://github.com/dart-lang/sdk/issues/60583
[#64035]: https://github.com/dart-lang/sdk/issues/64035

