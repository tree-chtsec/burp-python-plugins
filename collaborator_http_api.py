from burp import IBurpExtender, IExtensionStateListener
import sys
import json
import urlparse
import threading
import traceback
import SocketServer
import BaseHTTPServer

sys_stdout = sys.stdout
sys_stderr = sys.stderr

class BurpExtender(IBurpExtender, IExtensionStateListener):
    
    stdout = None
    ExtenderName = "Collaborator HTTP API"
    banner = "Python implementation of bit4woo/burp_collaborator_http_api"

    def registerExtenderCallbacks(self, callbacks):
        self.stderr = callbacks.getStderr()
        self.stdout = callbacks.getStdout()
        self.stdout.write(self.ExtenderName + "\n")
        self.stdout.write(self.banner + "\n")
        callbacks.setExtensionName(self.ExtenderName)
        callbacks.registerExtensionStateListener(self)
        self.ccc = callbacks.createBurpCollaboratorClientContext()
        self.helpers = callbacks.getHelpers()
        self.httpserver = apiServer(self, 8000)

    def extensionUnloaded(self):
        self.stdout.write("Extension unload\n")
        self.httpserver.exit()


class apiServer:

    def __init__(self, burpEx, port):
        class apiHandler(BaseHTTPServer.BaseHTTPRequestHandler):

            def do_GET(self):
                try:
                    if self.path.startswith('/generatePayload'):
                        # return: XYZ.burpcollaborator.net
                        self.generatePayload()
                    elif self.path.startswith('/fetchFor'):
                        # /fetchFor?payload=XYZ
                        self.fetchCollaboratorInteractionsFor()
                except Exception as e:
                    traceback.print_exc(file=burpEx.stderr)
                    burpEx.stderr.write(e.message)
                    self.send_response(500)
                    self.end_headers()
                    self.wfile.write(e.message)

            def do_POST(self):
                self.send_response(200)
                self.end_headers()

            def generatePayload(self):
                payload = burpEx.ccc.generatePayload(True)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(payload)

            def fetchCollaboratorInteractionsFor(self):
                params = urlparse.parse_qs(urlparse.urlparse(self.path).query)
                payload = params.get('payload', [None])[0]
                if payload is None:
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write("payload parameter missing")
                else:
                    bci = burpEx.ccc.fetchCollaboratorInteractionsFor(payload)
                    burpEx.stdout.write('%d record found:\n' % bci.size())
                    result = ''
                    for interaction in bci:
                        props = interaction.getProperties()
                        result += json.dumps(dict(props)) + "\n"
                        #burpEx.stdout.write(props.toString() + "\n")
                    self.send_response(200)
                    self.end_headers()
                    self.wfile.write(result)

            def log_message(self, _format, *args):
                burpEx.stdout.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), _format % args))

        self.host = '127.0.0.1'
        self.port = port
        self.burpEx = burpEx # instance above
        self.httpd = SocketServer.TCPServer((self.host, self.port), apiHandler)
        t = threading.Thread(target=self.start)
        t.start()

    def start(self):
        self.burpEx.stdout.write("Start serving on %s:%s\n" % (self.host, self.port))
        self.httpd.serve_forever()

    def exit(self):
        self.httpd.server_close()
