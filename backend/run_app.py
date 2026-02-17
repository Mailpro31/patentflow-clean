import os
import uvicorn

if __name__ == "__main__":
    # Get port from environment variable or default to 8000
    # This bypasses shell expansion issues in Docker/Railway
    port = int(os.environ.get("PORT", 8000))
    
    print(f"Starting PatentFlow Backend on port {port}")
    
    # Run Uvicorn programmatically
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        proxy_headers=True,  # Important for running behind proxy (Railway)
        forwarded_allow_ips="*"
    )
