{
  description = "omnipack";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs =
    { self, nixpkgs }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;
      pkgsFor = system: nixpkgs.legacyPackages.${system};
    in
    {
      # Building the shell proves every development tool still resolves.
      checks = forAllSystems (system: {
        devShell = self.devShells.${system}.default;
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          # Keep in step with requires-python in pyproject.toml.
          python = pkgs.python314;
        in
        {
          # Impure shell: uv manages .venv as usual, but with the nix interpreter.
          default = pkgs.mkShell {
            packages = [
              python
              pkgs.uv
              pkgs.just
              pkgs.lefthook
              pkgs.nodejs # commitlint runs through npx
              pkgs.actionlint
              pkgs.shellcheck # actionlint runs it on `run:` blocks
              pkgs.zizmor
              pkgs.lychee
            ];
            env = {
              UV_PYTHON = python.interpreter;
              UV_PYTHON_DOWNLOADS = "never";
            }
            // lib.optionalAttrs pkgs.stdenv.hostPlatform.isLinux {
              # Wheels with native code dlopen the manylinux libraries.
              LD_LIBRARY_PATH = lib.makeLibraryPath pkgs.pythonManylinuxPackages.manylinux1;
            };
            shellHook = ''
              unset PYTHONPATH
            '';
          };
        }
      );

      formatter = forAllSystems (system: (pkgsFor system).nixfmt-tree);
    };
}
