import progressbar
import time
from getpass import getpass
from halo import Halo


class HarmonyFormat():
    zarr = None


class Dataset():
    def __init__(self, dataset):
        self.dataset = dataset

    def info(self):
        pass

    def summary(self):
        pass

    def visualize(self):
        pass


class Spatial():
    def __init__(self, spatial):
        self.spatial = spatial
    
    def visualize(self):
        pass


class HarmonyRequest():

    format = HarmonyFormat

    def __init__(self, params=None):
        self.params = params
        self.dataset = Dataset(None)
        self.spatial = Spatial(None)

    def authenticate(self, username=None, password=None, netrc=None):
        if username is not None and password is None:
            password = getpass('Password: ')
            self._creds = {'username': username, 'password': password}
            print('\'username\' and \'password\' accepted.')


    @property
    def params(self):
        return self._params


    @params.setter
    def params(self, value):
        self._params = value


    def subset(self):
        print('Processing request:')
        for i in progressbar.progressbar(range(100)):
            time.sleep(0.08)
        print('Request processing complete.')


    @property
    def output(self):
        pass
