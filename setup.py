import setuptools

requirements = [
    "google-api-python-client",
    "lxml",
    "SQLAlchemy",
    "youtube_dl",
    "discord.py[voice]==1.3.4",
    "pydub",
    "aiohttp<3.7.0",
    "ffmpeg-python"
]

packages = setuptools.find_packages(where=".", include=["NerdyPy"])
if not packages:
    raise ValueError("No packages detected.")

setuptools.setup(
    name="NerpyBot",
    version="2.1",
    packages=packages,
    install_requires=requirements,
    url="https://github.com/nerdycraft/NerpyBot",
    license="GNU General Public License v3.0",
    author="Rico Wesenberg",
    author_email="",
    description="",
    zip_safe=False,
)
