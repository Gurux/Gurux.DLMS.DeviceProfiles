# Gurux DLMS Device Profiles

This repository contains device settings and profiles for different DLMS/COSEM meters. These profiles help configure communication with specific manufacturers, meter models, interfaces, and device variants.

## Directory structure

Profiles are organized by manufacturer, meter model, and interface type. An optional subdirectory identifies a specific device version or variant.

```text
<manufacturer>/<meter-model>/<InterfaceType>/<profile>.json
<manufacturer>/<meter-model>/<InterfaceType>/<device-variant>/<profile>.json
```

For example:

```text
EDMI/
└── Mk7MI/
    ├── HDLC/
    │   ├── Low.json
    │   └── None.json
    └── WRAPPER/
        ├── Low.json
        └── RDF_234/
            └── Low.json
```

The interface directory is required. The device variant directory is optional. Each profile JSON file contains an individual set of device settings.

## Interface types

Use the exact names, including capitalization, defined in the [Gurux DLMS InterfaceType enum](https://github.com/Gurux/Gurux.DLMS.Net/blob/master/Development/Enums/InterfaceType.cs).

Examples include `HDLC`, `WRAPPER`, and `HdlcWithModeE`.

GitHub Actions validates the interface directory against the official enum. If a profile contains an `InterfaceType` field, its value must match the directory, either as the enum name or its numeric value.

## Optional profile metadata

A profile can have a companion metadata file:

```text
EDMI/Mk7MI/HDLC/Low.json
EDMI/Mk7MI/HDLC/Low.meta.json
```

For example:

```json
{
  "Id": "edmi-mk7mi-hdlc-low",
  "Name": "Low HDLC",
  "Revision": "1.0.0"
}
```

A permanent `Id` is recommended. Preserve it when renaming or moving the profile and its metadata file.

Without metadata, the display name is derived from the filename and the identifier is derived from its path. The profile revision is separate from the meter’s device version or variant.

## Contributing

Anyone can contribute new device profiles or improvements to existing profiles.

To submit a profile:

1. Fork this repository.
2. Add the JSON settings file to the appropriate directory.
3. Add a companion metadata file with a permanent identifier where possible.
4. Open a pull request describing the meter and the settings you have tested.

Submitted profiles are reviewed before being accepted. **Once a profile is approved, merged, and successfully published, it is made available to everyone.**

By submitting device profiles or associated metadata, you agree to dedicate your contributions under **CC0 1.0 Universal**. You must have the right to make this dedication. Do not submit material whose third-party licensing or confidentiality restrictions prevent its publication under CC0.

Do not include passwords, encryption keys, or other confidential information.

When removing a profile, also remove its companion metadata file, if present.

## Validation and publication

GitHub Actions validates profiles before generating and publishing the index. Checks include JSON structure, configured size limits, interface types, metadata, and supported formula syntax.

These checks do not replace testing with the intended meter or validation by the application that uses the profile.

## Profile index

The `manufacturers.json` index is generated automatically using this hierarchy:

```text
Manufacturers → Models → Interfaces → Versions → Settings
```

The index uses `SchemaVersion: 2` and includes download URLs, SHA-256 checksums, and file sizes. Applications can discover available profiles and download only the settings they need.

The index is regenerated when profiles are added, changed, or removed. Removing a profile from the repository removes it from the next successfully published index; it does not automatically remove copies already installed by users.

## License

The device profiles, associated profile metadata, and generated profile index are dedicated to the public domain under [CC0 1.0 Universal](https://creativecommons.org/publicdomain/zero/1.0/).

You may copy, modify, and redistribute this material, including for commercial purposes, without requesting permission or providing attribution. Attribution to Gurux and profile contributors is appreciated but not required.

The material is provided without warranties, to the fullest extent permitted by applicable law. CC0 does not grant patent or trademark rights or imply endorsement by Gurux or any meter manufacturer.

This CC0 dedication applies to profile data and the generated index. Scripts, workflows, and third-party source files are governed by their separately stated licenses and are not covered by this dedication.