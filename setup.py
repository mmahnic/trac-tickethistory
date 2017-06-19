# vim: set fileencoding=utf-8 sw=4 sts=4 ts=8 et :vim
import os
from setuptools import setup, find_packages

setup(
        name = 'TicketHistory',
        version = '0.1',
        description = "Various plugins that display the history of a group of tickets in a time interval",
        long_description = open(os.path.join(os.path.dirname(__file__), 'README.md')).read(),
        classifiers = [
                'Development Status :: 1 - Planning',
                'Environment :: Plugins',
                'Environment :: Web Environment',
                'Framework :: Trac',
                'License :: OSI Approved :: MIT License',
                'Natural Language :: English',
                'Programming Language :: Python'
                ],
        keywords = 'trac plugin history board',
        author = 'Marko Mahnič',
        author_email = '',
        url = 'http://github.com/mmahnic/ticket-history',
        license = 'MIT License',
        packages = find_packages(exclude=['ez_setup', 'examples', 'tickethistory.test']),
        package_data = {
                'tickethistory': [
                        'templates/*.html',
                        'htdocs/css/*.css',
                        'htdocs/css/images/*.png',
                        'htdocs/js/*.js',
                        'htdocs/js/libs/*.js'
                        ]
                },
        include_package_data = True,
        zip_safe = False,
        install_requires = ['Trac'],
        entry_points = """
        [trac.plugins]
        tickethistory = tickethistory
    """,
)
