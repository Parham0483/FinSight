from rest_framework.renderers import JSONRenderer
import json


class EnvelopeRenderer(JSONRenderer):
    """Wraps all API responses in {success, data, meta/error} envelope."""

    def render(self, data, accepted_media_type=None, renderer_context=None):
        if renderer_context is None:
            return super().render(data, accepted_media_type, renderer_context)

        response = renderer_context.get('response')
        if response is None:
            return super().render(data, accepted_media_type, renderer_context)

        status_code = response.status_code
        success = status_code < 400

        if success:
            # DRF pagination wraps data in {count, next, previous, results}
            if isinstance(data, dict) and 'results' in data:
                envelope = {
                    'success': True,
                    'data': data['results'],
                    'meta': {
                        'pagination': {
                            'total': data.get('count'),
                            'next': data.get('next'),
                            'previous': data.get('previous'),
                        }
                    },
                }
            else:
                envelope = {'success': True, 'data': data}
        else:
            envelope = {
                'success': False,
                'error': {
                    'code': _derive_error_code(data),
                    'message': _derive_message(data),
                    'field_errors': _derive_field_errors(data),
                },
            }

        return json.dumps(envelope).encode()


def _derive_error_code(data: dict) -> str:
    if isinstance(data, dict):
        return data.get('code', 'ERROR')
    return 'ERROR'


def _derive_message(data: dict) -> str:
    if isinstance(data, dict):
        if 'detail' in data:
            return str(data['detail'])
        if 'non_field_errors' in data:
            errors = data['non_field_errors']
            return errors[0] if errors else 'Validation error'
        if 'message' in data:
            return str(data['message'])
    return 'An error occurred'


def _derive_field_errors(data: dict) -> dict:
    if not isinstance(data, dict):
        return {}
    excluded = {'detail', 'code', 'message', 'non_field_errors'}
    return {k: v for k, v in data.items() if k not in excluded}
