from nikolasigmoid/py-mcp-proxy:latest

copy src src 
copy pyproject.toml pyproject.toml
copy config.json config.json

run python -m pip install . && rm -rf pyproject.toml