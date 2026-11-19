# Native C++ client and C ABI probe

These clients link the installed communication SDK and do not start Python. The
C++ client discovers a running CyTool through authenticated HTTP; the service keeps
its own engine/runtime, which may be Python.

```sh
cmake -S Examples/NativeClient -B build/native-client -DCMAKE_PREFIX_PATH=PATH_TO_NATIVE_INSTALL
cmake --build build/native-client --config Release
```

Run `cytools_cpp_client` without arguments for ABI/version information. For a real
service, set `CYTOOLS_TOKEN` in the environment and pass its loopback `/v1` URL as
the sole argument. Credentials are not passed on the command line. Run
`cytools_c_abi_probe` to check that a plain C program can include and link the ABI.

See [Native communication](../../Docs/NativeCommunication.md) for build/install,
host callback lifecycle, identity and redistribution notices.
