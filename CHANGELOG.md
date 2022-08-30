# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

### Fixed
- saw many collisions when working on bus with multiple MFCs, added wait in write queue
- MFCs will report busy if position is different than destination
- pinned hart-protocol to ensure upstream fixes applied here

## [2022.8.1]

### Changed
- pin to new version of hart-protocol

### Fixed
- problem where position was never read from MFC

## [2022.8.0]

### Added
- initial release

[Unreleased]: https://github.com/yaq-project/yaqd-brooks/-/compare/v2022.8.1...main
[2022.8.1]: https://github.com/yaq-project/yaqd-brooks/-/compare/v2022.8.0...v2022.8.1
[2022.8.0]: https://github.com/yaq-project/yaqd-brooks/-/tags/v2022.8.0

