{
  description = "DevOps Info Service - Reproducible build with Nix Flakes (IU DevOps Lab 18)";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-24.11";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        app = import ./default.nix { inherit pkgs; };
        dockerImage = import ./docker.nix { inherit pkgs; };
      in
      {
        packages = {
          default = app;
          devops-info-service = app;
          dockerImage = dockerImage;
        };

        apps.default = {
          type = "app";
          program = "${app}/bin/devops-info-service";
        };

        devShells.default = pkgs.mkShell {
          name = "devops-info-service-dev";

          buildInputs = with pkgs; [
            python3
            python3Packages.flask
            python3Packages.python-json-logger
            python3Packages.prometheus-client
            python3Packages.pytest
            python3Packages.pip
            docker-client
            curl
            jq
          ];

          shellHook = ''
            echo "============================================"
            echo "  devops-info-service dev shell (Lab 18)"
            echo "============================================"
            echo "Python    : $(python3 --version)"
            echo "Flask     : $(python3 -c 'import flask; print(flask.__version__)')"
            echo "Prometheus: $(python3 -c 'import prometheus_client; print(prometheus_client.__version__)')"
            echo "Run with  : python3 app.py"
            echo "============================================"
          '';
        };

        formatter = pkgs.nixpkgs-fmt;
      });
}
