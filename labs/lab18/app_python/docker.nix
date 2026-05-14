{ pkgs ? import <nixpkgs> {} }:

let
  app = import ./default.nix { inherit pkgs; };
in
pkgs.dockerTools.buildLayeredImage {
  name = "devops-info-service-nix";
  tag = "1.0.0";

  contents = [
    app
    pkgs.cacert
    pkgs.coreutils
    pkgs.bash
  ];

  config = {
    Entrypoint = [ "${app}/bin/devops-info-service" ];
    Cmd = [];

    ExposedPorts = {
      "5000/tcp" = {};
    };

    Env = [
      "HOST=0.0.0.0"
      "PORT=5000"
      "DATA_DIR=/data"
      "CONFIG_PATH=/config/config.json"
      "PYTHONUNBUFFERED=1"
      "PATH=/bin:/usr/bin"
      "SSL_CERT_FILE=${pkgs.cacert}/etc/ssl/certs/ca-bundle.crt"
    ];

    Labels = {
      "org.opencontainers.image.title" = "devops-info-service";
      "org.opencontainers.image.version" = "1.0.0";
      "org.opencontainers.image.source" = "https://github.com/iamkoldun/devops";
      "org.opencontainers.image.description" = "Reproducible Nix-built image for IU DevOps Lab 18";
    };

    WorkingDir = "/";

    User = "1000:1000";
  };

  created = "1970-01-01T00:00:01Z";

  maxLayers = 100;
}
