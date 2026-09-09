from http.server import HTTPServer, BaseHTTPRequestHandler
import os

class MockERPHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if os.getenv("SIMULATE_DOWN", "false").lower() == "true":
            self.send_response(503)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"error": "ERP Gateway Unavailable / Maintenance"}')
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b'{"status": "success", "erp_doc_id": "ERP-MOCK-RECORD-001"}')

    def log_message(self, format, *args):
        # Clean console logging
        print(f"[Mock ERP] {self.address_string()} - {format % args}")

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 8080), MockERPHandler)
    print("Mock ERP running on port 8080...")
    server.serve_forever()