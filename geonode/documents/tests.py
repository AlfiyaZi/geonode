"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

"""
import StringIO
import json

from django.test import TestCase
from django.conf import settings
from django.test.client import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.core.urlresolvers import reverse

from .forms import DocumentCreateForm

from geonode.maps.models import Map
from geonode.documents.models import Document
from geonode.security.enumerations import ANONYMOUS_USERS, AUTHENTICATED_USERS
import geonode.documents.views
import geonode.security
from geonode.search.populate_search_test_data import create_models


class LayersTest(TestCase):
    fixtures = ['intial_data.json', 'bobby']
    
    def setUp(self):
        create_models('document')
        create_models('map')
        self.imgfile = StringIO.StringIO('GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00'
                                         '\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')

    def test_create_document_with_no_rel(self):
        """Tests the creation of a document with no relations"""

        f = SimpleUploadedFile('test_img_file.gif', self.imgfile.read(), 'image/gif')
    
        superuser = User.objects.get(pk=2)
        c = Document.objects.create(doc_file=f,owner=superuser, title='theimg')
        c.set_default_permissions()
        document = Document.objects.get(pk=c.id)
        self.assertEquals(Document.objects.get(pk=c.id).title, 'theimg')

    def test_create_document_with_rel(self):
        """Tests the creation of a document with no a map related"""
        f = SimpleUploadedFile('test_img_file.gif', self.imgfile.read(), 'image/gif')
    
        superuser = User.objects.get(pk=2)
        
        m = Map.objects.all()[0]
        ctype = ContentType.objects.get_for_model(m)

        c = Document.objects.create(doc_file=f,owner=superuser, 
            title='theimg', content_type=ctype, object_id=m.id)

        self.assertEquals(Document.objects.get(pk=c.id).title, 'theimg')

    def test_create_document_url(self):
        """Tests creating an external document instead of a file."""

        superuser = User.objects.get(pk=2)
        c = Document.objects.create(doc_url="http://geonode.org/map.pdf",
                                    owner=superuser,
                                    title="GeoNode Map",
                                    )
        doc = Document.objects.get(pk=c.id)
        self.assertEquals(doc.title, "GeoNode Map")
        self.assertEquals(doc.extension, "pdf")

    def test_create_document_url_view(self):
        """
        Tests creating and updating external documents.
        """
        superuser = User.objects.get(pk=2)

        c = Client()
        c.login(username='admin', password='admin')
        form_data = {'title': 'GeoNode Map',
                     'permissions': '{"anonymous":"document_readonly","authenticated":"document_readwrite","users":[]}',
                     'doc_url': 'http://www.geonode.org/map.pdf'
                     }

        response = c.post(reverse('document_upload'), data=form_data)
        self.assertEqual(response.status_code, 302)

        d = Document.objects.get(title='GeoNode Map')
        self.assertEqual(d.doc_url, 'http://www.geonode.org/map.pdf')

        form_data['doc_url'] = 'http://www.geonode.org/mapz.pdf'
        response = c.post(reverse('document_replace', args=[d.id]), data=form_data)
        self.assertEqual(response.status_code, 302)

        d = Document.objects.get(title='GeoNode Map')
        self.assertEqual(d.doc_url, 'http://www.geonode.org/mapz.pdf')

    def test_upload_document_form(self):
        """
        Tests the Upload form.
        """
        form_data = dict()
        form = DocumentCreateForm(data=form_data)
        self.assertFalse(form.is_valid())

        # title is required
        self.assertTrue('title' in form.errors)

        # permissions are required
        self.assertTrue('permissions' in form.errors)

        # since neither a doc_file nor a doc_url are included __all__ should be in form.errors.
        self.assertTrue('__all__' in form.errors)

        form_data = {'title': 'GeoNode Map',
                     'permissions': '{"anonymous":"document_readonly","authenticated":"document_readwrite","users":[]}',
                     'doc_url': 'http://www.geonode.org/map.pdf'
                     }

        form = DocumentCreateForm(data=form_data)
        self.assertTrue(form.is_valid())

        self.assertTrue(isinstance(form.cleaned_data['permissions'], dict))

        # if permissions are not JSON serializable, the field should be in form.errors.
        form_data['permissions'] = 'non-json string'
        self.assertTrue('permissions' in DocumentCreateForm(data=form_data).errors)

        form_data = {'title': 'GeoNode Map',
                     'permissions': '{"anonymous":"document_readonly","authenticated":"document_readwrite","users":[]}',
                     }

        file_data = {'doc_file': SimpleUploadedFile('test_img_file.gif', self.imgfile.read(), 'image/gif')}
        form = DocumentCreateForm(form_data, file_data)
        self.assertTrue(form.is_valid())

        # The form should raise a validation error when a url and file is present.
        form_data['doc_url'] = 'http://www.geonode.org/map.pdf'
        form = DocumentCreateForm(form_data, file_data)
        self.assertFalse(form.is_valid())
        self.assertTrue('__all__' in form.errors)

    def test_document_details(self):
        """/documents/1 -> Test accessing the detail view of a document"""

    
        superuser = User.objects.get(pk=2)
        d = Document.objects.get(pk=1)
        d.set_default_permissions()

        c = Client()
        response = c.get(reverse('document_detail', args=(str(d.id),)))
        self.assertEquals(response.status_code, 200)

    def test_access_document_upload_form(self):
        """Test the form page is returned correctly via GET request /documents/upload"""

        c = Client()
        log = c.login(username='bobby', password='bob')
        self.assertTrue(log)
        response = c.get(reverse('document_upload'))
        self.assertTrue('Upload Documents' in response.content)


    def test_document_isuploaded(self):
        """/documents/upload -> Test uploading a document"""

        f = SimpleUploadedFile('test_img_file.gif', self.imgfile.read(), 'image/gif')
        m = Map.objects.all()[0]        
        c = Client()
        
        c.login(username='admin', password='admin')
        response = c.post(reverse('document_upload'), data={'file': f, 'title': 'uploaded_document', 'q': m.id, 'type': 'map', 
            'permissions': '{"anonymous":"document_readonly","users":[]}'},
                          follow=True)
        self.assertEquals(response.status_code, 200)

        
    # Permissions Tests

    # Users
    # - admin (pk=2)
    # - bobby (pk=1)

    # Inherited
    # - LEVEL_NONE = _none

    # Layer
    # - LEVEL_READ = document_read
    # - LEVEL_WRITE = document_readwrite
    # - LEVEL_ADMIN = document_admin
    

    # FIXME: Add a comprehensive set of permissions specifications that allow us 
    # to test as many conditions as is possible/necessary
    
    # If anonymous and/or authenticated are not specified, 
    # should set_layer_permissions remove any existing perms granted??
    
    perm_spec = {"anonymous":"_none","authenticated":"_none","users":[["admin","document_readwrite"]]}
    
    def test_set_document_permissions(self):
        """Verify that the set_document_permissions view is behaving as expected
        """
        f = SimpleUploadedFile('test_img_file.gif', self.imgfile.read(), 'image/gif')
    
        superuser = User.objects.get(pk=2)
        # Get a document to work with
        document = Document.objects.all()[0]
       
        # Set the Permissions
        document.set_permissions(self.perm_spec)

        # Test that the Permissions for ANONYMOUS_USERS and AUTHENTICATED_USERS were set correctly        
        self.assertEqual(document.get_gen_level(ANONYMOUS_USERS), document.LEVEL_NONE) 
        self.assertEqual(document.get_gen_level(AUTHENTICATED_USERS), document.LEVEL_NONE)

        # Test that previous permissions for users other than ones specified in
        # the perm_spec (and the document owner) were removed
        users = [n for (n, p) in self.perm_spec['users']]
        levels = document.get_user_levels().exclude(user__username__in = users + [document.owner])
        self.assertEqual(len(levels), 0)
       
        # Test that the User permissions specified in the perm_spec were applied properly
        for username, level in self.perm_spec['users']:
            user = geonode.maps.models.User.objects.get(username=username)
            self.assertEqual(document.get_user_level(user), level)    

    def test_ajax_document_permissions(self):
        """Verify that the ajax_document_permissions view is behaving as expected
        """
    
        # Setup some document names to work with 
        f = SimpleUploadedFile('test_img_file.gif', self.imgfile.read(), 'image/gif')
    
        superuser = User.objects.get(pk=2)
        document = Document.objects.create(doc_file=f,owner=superuser, title='theimg')
        document.set_default_permissions()
        document_id = document.id
        invalid_document_id = 20
        
        c = Client()

        # Test that an invalid document is handled for properly
        response = c.post(reverse('resource_permissions', args=('document', invalid_document_id,)), 
                            data=json.dumps(self.perm_spec),
                            content_type="application/json")
        self.assertEquals(response.status_code, 404) 

        # Test that GET returns permissions
        response = c.get(reverse('resource_permissions', args=('document', document_id,)))
        assert('permissions' in response.content)
        
        # Test that a user is required to have documents.change_layer_permissions

        # First test un-authenticated
        response = c.post(reverse('resource_permissions', args=('document', document_id,)), 
                            data=json.dumps(self.perm_spec),
                            content_type="application/json")
        self.assertEquals(response.status_code, 401) 

        # Next Test with a user that does NOT have the proper perms
        logged_in = c.login(username='bobby', password='bob')
        self.assertEquals(logged_in, True) 
        response = c.post(reverse('resource_permissions', args=('document', document_id,)), 
                            data=json.dumps(self.perm_spec),
                            content_type="application/json")
        self.assertEquals(response.status_code, 401) 

        # Login as a user with the proper permission and test the endpoint
        logged_in = c.login(username='admin', password='admin')
        self.assertEquals(logged_in, True)
        response = c.post(reverse('resource_permissions', args=('document', document_id,)), 
                            data=json.dumps(self.perm_spec),
                            content_type="application/json")

        # Test that the method returns 200         
        self.assertEquals(response.status_code, 200)

