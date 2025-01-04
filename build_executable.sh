
#!/bin/bash

# Build executables using tox
tox -e build

# Move executables to the desktop
mv dist/* ~/Desktop/