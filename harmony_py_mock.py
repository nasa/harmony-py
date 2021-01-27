import progressbar
import time
from getpass import getpass
from halo import Halo


class HarmonyRequest():

    def __init__(self, params=None):
        self.params = params


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


    def submit(self):
        # spinner = Halo(text='Processing request... ', spinner='dots')
        # spinner.start()
        # time.sleep(5)
        # spinner.stop()
        print('Processing request:')
        for i in progressbar.progressbar(range(100)):
            time.sleep(0.08)
        print('Request processing complete.')


    @property
    def output(self):
        pass