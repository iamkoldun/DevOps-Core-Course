{ pkgs ? import <nixpkgs> {} }:

pkgs.python3Packages.buildPythonApplication {
  pname = "devops-info-service";
  version = "1.0.0";

  src = ./.;

  format = "other";

  propagatedBuildInputs = with pkgs.python3Packages; [
    flask
    python-json-logger
    prometheus-client
  ];

  nativeBuildInputs = [ pkgs.makeWrapper ];

  dontUnpack = false;
  doCheck = false;

  installPhase = ''
    runHook preInstall

    mkdir -p $out/bin $out/share/devops-info-service
    cp app.py $out/share/devops-info-service/app.py

    makeWrapper ${pkgs.python3}/bin/python3 $out/bin/devops-info-service \
      --add-flags "$out/share/devops-info-service/app.py" \
      --prefix PYTHONPATH : "$PYTHONPATH" \
      --set-default HOST "0.0.0.0" \
      --set-default PORT "5000"

    runHook postInstall
  '';

  meta = with pkgs.lib; {
    description = "DevOps Info Service - reproducible Nix build of Lab 1 Flask app";
    homepage = "https://github.com/iamkoldun/devops";
    license = licenses.mit;
    platforms = platforms.unix;
    mainProgram = "devops-info-service";
  };
}
