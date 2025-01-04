
#!/bin/bash

EXECUTABLES=("sensorcommunity_combined" "combined" "all-in-one-no-pm" "all-in-one-enviro-mini")

DESKTOP_DIR=~/Desktop

for exe in "${EXECUTABLES[@]}"; do
    cat <<EOF > "$DESKTOP_DIR/$exe.desktop"
[Desktop Entry]
Type=Application
Name=$exe
Exec=$PWD/dist/$exe
Icon=utilities-terminal
Terminal=true
EOF
    chmod +x "$DESKTOP_DIR/$exe.desktop"
done