{
  description = "omnipack";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    pyproject-nix = {
      url = "github:pyproject-nix/pyproject.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    uv2nix = {
      url = "github:pyproject-nix/uv2nix";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    pyproject-build-systems = {
      url = "github:pyproject-nix/build-system-pkgs";
      inputs.pyproject-nix.follows = "pyproject-nix";
      inputs.uv2nix.follows = "uv2nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
  };

  outputs =
    {
      self,
      nixpkgs,
      pyproject-nix,
      uv2nix,
      pyproject-build-systems,
      ...
    }:
    let
      inherit (nixpkgs) lib;
      forAllSystems = lib.genAttrs lib.systems.flakeExposed;
      pkgsFor = system: nixpkgs.legacyPackages.${system};
      workspace = uv2nix.lib.workspace.loadWorkspace { workspaceRoot = ./.; };
      # Lowest interpreter satisfying requires-python (matches the CI matrix
      # floor); the uv2nix template simply uses pkgs.python3.
      pythonFor =
        pkgs:
        lib.head (
          pyproject-nix.lib.util.filterPythonInterpreters {
            inherit (workspace) requires-python;
            inherit (pkgs) pythonInterpreters;
          }
        );
      # Wheels need no build overrides; sdists usually do.
      overlay = workspace.mkPyprojectOverlay { sourcePreference = "wheel"; };
      pythonSetFor =
        pkgs:
        (pkgs.callPackage pyproject-nix.build.packages { python = pythonFor pkgs; }).overrideScope (
          lib.composeManyExtensions [
            pyproject-build-systems.overlays.wheel
            overlay
          ]
        );
    in
    {
      packages = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          pythonSet = pythonSetFor pkgs;
          inherit (pkgs.callPackages pyproject-nix.build.util { }) mkApplication;
          # Only bin/ and data files ship; the interpreter and venv scaffolding do not.
          app = mkApplication {
            venv = pythonSet.mkVirtualEnv "omnipack-env" workspace.deps.default;
            package = pythonSet."omnipack";
          };
        in
        {
          default = app;
          docker = pkgs.dockerTools.streamLayeredImage {
            name = "omnipack";
            tag = "latest";
            contents = [ app ];
            config.Cmd = [ "${app}/bin/pack" ];
          };
        }
      );

      checks = forAllSystems (system: {
        build = self.packages.${system}.default;
      });

      devShells = forAllSystems (
        system:
        let
          pkgs = pkgsFor system;
          python = pythonFor pkgs;
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
