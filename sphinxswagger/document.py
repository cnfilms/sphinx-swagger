try:
    import http.client as http_client
except ImportError:
    import httplib as http_client




class SwaggerDocument(object):

    def __init__(self):
        super(SwaggerDocument, self).__init__()
        self._definitions = {}
        self._paths = {}

    def get_document(self, config):
        """
        :param sphinx.config.Config config: project level configuration
        :return: the swagger document as a :class:`dict`
        :rtype: dict
        """
        info = {'title': config.project,
                'description': config.swagger_description,
                'license': config.swagger_license,
                'version': config.version}
        if not info['description'] and hasattr(config, 'html_theme_options'):
            info['description'] = config.html_theme_options.get('description')

        auth_header_label = config._raw_config.get('auth_header_label', 'Authorization')
        is_local = config._raw_config.get('is_local', False)
        host = config._raw_config.get('host', 'localhost:8080')

        return {
            'openapi': '3.0.3',
            'info': info,
            'servers': [{'url': f"{'https' if not is_local else 'http'}://{host}"}],
            'components': {
                'securitySchemes': {
                    'JWT': {
                        'type': 'apiKey',
                        'name': auth_header_label,
                        'in': 'header',
                    }
                },
                'schemas': self._definitions,
            },
            'security': [
                {'JWT': []}
            ],
            'paths': self._paths,
        }

    def add_endpoint(self, endpoint, debug_info=False):
        """
        Add a swagger endpoint document.

        :param SwaggerEndpoint endpoint: the endpoint to add
        :param dict debug_info: optional debug information to include
            in the swagger definition

        """
        if type(endpoint) == SwaggerEndpoint:
            path_info = self._paths.setdefault(endpoint.uri_template, {})
            if endpoint.method in path_info:
                pass  # already gots this ... good this isn't
            path_info[endpoint.method] = endpoint.generate_swagger()
        elif type(endpoint) == SwaggerDefinition:
            self._definitions[endpoint.object_name] = endpoint.generate_swagger()

        # if debug_info:
        #     path_info[endpoint.method]['x-debug-info'] = debug_info

class SwaggerDefinition(object):
    def __init__(self):
        self.object_name = None
        self.object_type = 'object'
        self.object_properties = {}
        self.properties_required = []

    def generate_swagger(self):
        swagger = {}
        swagger = {'type': self.object_type, 'properties': self.object_properties}

        return swagger

class SwaggerEndpoint(object):

    def __init__(self):
        self.method = None
        self.uri_template = None
        self.summary = ''
        self.tags = list()
        self.description = ''
        self.parameters = []
        self.request_body = None
        self.responses = {}
        self.default_response_schema = None
        self.response_headers = None

    def set_default_response_structure(self, properties, is_array=False):
        schema = {'type': 'object', 'properties': {}, 'required': []}
        for prop in properties:
            name = prop.pop('name')
            schema['properties'][name] = prop.copy()
            schema['required'].append(name)
        if is_array:
            schema = {'type': 'array', 'items': schema}
        self.default_response_schema = schema

    def add_request_headers(self, headers):
        for name, description in headers.items():
            self.parameters.append({
                'name': name,
                'description': description,
                'in': 'header',
                'schema': {'type': 'string'},
            })

    def add_response_headers(self, headers):
        self.response_headers = {
            name: {'description': description, 'type': 'string'}
            for name, description in headers.items()
        }

    def add_response_codes(self, status_dict):
        for code, info in status_dict.items():
            swagger_rsp = self.responses.setdefault(code, {})
            if not info['reason']:
                try:
                    code = int(code)
                    info['reason'] = http_client.responses[code]
                except (KeyError, TypeError, ValueError):
                    info['reason'] = 'Unknown'

            tokens = info['description'].split(maxsplit=2)
            if tokens:
                tokens[0] = tokens[0].title()
            swagger_rsp['description'] = '{}\n\n{}'.format(
                info['reason'], ' '.join(tokens)).strip()

    def generate_swagger(self):
        swagger = {'summary': self.summary, 'description': self.description, 'tags': self.tags}
        if self.parameters:
            swagger['parameters'] = self.parameters
        if self.request_body:
            swagger['requestBody'] = self.request_body

        if self.responses:
            swagger['responses'] = self.responses
        else:  # openapi requires at least one response
            swagger['responses'] = {'default': {'description': ''}}

        default_code = 'default'
        status_codes = sorted(int(code)
                              for code in swagger['responses']
                              if code.isdigit())
        for code in status_codes:
            if 200 <= code < 400:
                default_code = str(code)
                break

        if default_code in swagger['responses']:
            if self.default_response_schema:
                swagger['responses'][default_code]['content'] = {
                    'application/json': {
                        'schema': self.default_response_schema
                    }
                }
            if self.response_headers:
                oa_headers = {}
                for hname, hinfo in self.response_headers.items():
                    oa_headers[hname] = {'schema': hinfo}
                swagger['responses'][default_code]['headers'] = oa_headers

        return swagger
