docker build -t arxiv-mcp-server .
docker run  --rm -it \
    --network=network-agent-external  \
    --add-host=localmodel:host-gateway \
    -p 7000:80 \
    -e LLM_BASE_URL="$LLM_BASE_URL" \
    -e LLM_API_KEY="$LLM_API_KEY" \
    -e LLM_MODEL_ID="$LLM_MODEL_ID" \
    -e DEBUG_MODE="true" \
    -e LOCAL_TEST=1 \
    arxiv-mcp-server
