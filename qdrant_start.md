 # Start docker with command:
 systemctl start docker

 # Start qdrant server:
 sudo docker run -p 6333:6333 -p 6334:6334 qdrant/qdrant

 # qdrant mcp server
 clone the repo from github 
 cd in the repo and run the command: sudo docker build -t mcp-server-qdrant .

 run the docker command to start the mcp-server on docker:
 sudo docker run -p 8000:8000 \
  --add-host=host.docker.internal:host-gateway \
  -e FASTMCP_HOST="0.0.0.0" \
  -e QDRANT_URL="http://host.docker.internal:6333" \
  -e COLLECTION_NAME="resume_chunks" \
  mcp-server-qdrant
