import io
import zipfile
import unittest
from PIL import Image
from app import app


def image_bytes(size=(100, 150), color='red'):
    stream = io.BytesIO()
    Image.new('RGB', size, color).save(stream, 'PNG')
    stream.seek(0)
    return stream


class ConverterTests(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def test_home(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'PanelForge', response.data)

    def test_image_to_cbz(self):
        response = self.client.post('/convert', data={
            'files': (image_bytes(), 'page01.png'),
            'output_name': 'chapter', 'format': 'jpeg', 'quality': '85',
            'direction': 'rtl', 'title': 'Test Chapter'
        }, content_type='multipart/form-data')
        self.assertEqual(response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(response.data)) as archive:
            self.assertEqual(archive.namelist(), ['000001.jpg', 'ComicInfo.xml'])
            self.assertIn(b'Test Chapter', archive.read('ComicInfo.xml'))

    def test_spread_split_rtl(self):
        response = self.client.post('/convert', data={
            'files': (image_bytes((300, 100)), 'spread.png'),
            'format': 'png', 'split_spreads': 'on', 'direction': 'rtl'
        }, content_type='multipart/form-data')
        self.assertEqual(response.headers['X-Page-Count'], '2')

    def test_rejects_empty_request(self):
        response = self.client.post('/convert')
        self.assertEqual(response.status_code, 400)


if __name__ == '__main__':
    unittest.main()
