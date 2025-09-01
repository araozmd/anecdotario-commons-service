from setuptools import setup, find_packages

setup(
    name="anecdotario-commons",
    version="1.0.0",
    description="Shared utilities and models for Anecdotario microservices",
    author="Anecdotario Team",
    author_email="dev@anecdotario.com",
    packages=find_packages(),
    install_requires=[
        "boto3>=1.34.0",
        "pynamodb>=6.0.0",
        "Pillow>=10.0.0",
        "python-dotenv>=1.0.0",
    ],
    python_requires=">=3.12",
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3.12",
    ],
)