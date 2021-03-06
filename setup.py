import setuptools

requirements = [
    "google-api-python-client",
    "SQLAlchemy",
    "youtube_dl",
    "discord.py[voice]==1.5.1",
    "pydub",
    "ffmpeg-python",
    "python-wowapi==4.0.0"
]

packages = setuptools.find_packages(where=".", include=["NerdyPy"])
if not packages:
    raise ValueError("No packages detected.")

setuptools.setup(
    name="NerpyBot",
    version="0.2.6",
    packages=packages,
    install_requires=requirements,
    url="https://github.com/nerdycraft/NerpyBot",
    license="GNU General Public License v3.0",
    author="Rico Wesenberg",
    author_email="",
    description="",
    zip_safe=False,
)
