# Project description

This project is my vision of how curriculum vitae (CV or Resume) should look to help
the organizations and those who are looking for a job to find each other.

This vision is the thoughts of developer/engineer how it can be implemented to be maximum helpful for
consumer to automate matching, minimize CV capacity and maximize the number of representations of the final view.

All code based on next two main frameworks - Django and Django REST framework

Also, It embraces all the main aspects of software development for REST API:
- Database (planning, normalization ...)
- Database constraints/logical integrity (to check the date ranges crossing, for example)
- Creating the serializators with control over both some restrictions and integrity checking at this level.
- Creating the views (it does not embrace ViewSet-s) that behave like a ViewSet with some additional checks at this level.
- Testing all parts of described above. Both simple tests like "what I think is what I write" and tests that follow the the DRY methodology and should probably be tested as well :)

This project was started to achieve two main goals:
- Acquire practice/confidence and learn more about the components of the Django REST Framework.
- Automate the generation of my own CV in various forms (representations)

Thus, Some code was refactored during my developing but some code was not.
In anyway all works properly and the tests prove it.

# What the project has and has not, in short

## Project has:
- Implemented the ready to use DB structure
- RESTful API with login through session authentication (Ajax)
- For simplification, SQLite was used

## Project has not:
- Any implemented representations
- Any UI
- Sign Up user (you can create a user using Django Admin or manually in code using a model)

# Installation and Dependencies

## Prepare virtual environment
- Go to current work dir
    ```
    $ cd ~/Python.projects/cv/
    ```

- Make virtual environment 
    ```
    ~/Python.projects/cv$ python3 -m venv .venv
    ```
- Activate virtual environment
    ```
    ~/Python.projects/cv$ source [tab+tab]
    apps/       cv_project/ db.sqlite3  .gitignore  manage.py   media/      README.md   .venv/

    ~/Python.projects/cv$ source .venv/bin/activate
    ```
- Update PIP of virtual environment (optional)
    ```
    (.venv) ~/Python.projects/cv$ pip install pip -U
    Requirement already satisfied: pip in ./.venv/lib/python3.9/site-packages (20.3.4)
    Collecting pip
      Using cached pip-23.2.1-py3-none-any.whl (2.1 MB)
    Installing collected packages: pip
      Attempting uninstall: pip
        Found existing installation: pip 20.3.4
        Uninstalling pip-20.3.4:
          Successfully uninstalled pip-20.3.4
    Successfully installed pip-23.2.1
    ```

## Install dependencies using requirements.txt
```
pip install -r /path/to/requirements.txt
```

## Manual installation of dependencies

### List of dependencies (overview)
- Main (required)
    - [Django](https://www.djangoproject.com/)
        - [Pillow](https://pillow.readthedocs.io/en/stable/)
    - [Django REST framework](https://www.django-rest-framework.org/)
- Testing (optional)
    - [Beautyfulsoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
        - [lxml](https://lxml.de/)
    - [Requests](https://requests.readthedocs.io/en/latest/)

### Manual installation with the console output (TLDR; [go further](#rights-like-license))

- [Django](https://www.djangoproject.com/ "Django")
```
(.venv) ~/Python.projects/cv$ pip install django
Collecting django
  Obtaining dependency information for django from https://files.pythonhosted.org/packages/bf/8b/c38f2354b6093d9ba310a14b43a830fdf776edd60c2e25c7c5f4d23cc243/Django-4.2.5-py3-none-any.whl.metadata
  Downloading Django-4.2.5-py3-none-any.whl.metadata (4.1 kB)
Collecting asgiref<4,>=3.6.0 (from django)
  Obtaining dependency information for asgiref<4,>=3.6.0 from https://files.pythonhosted.org/packages/9b/80/b9051a4a07ad231558fcd8ffc89232711b4e618c15cb7a392a17384bbeef/asgiref-3.7.2-py3-none-any.whl.metadata
  Downloading asgiref-3.7.2-py3-none-any.whl.metadata (9.2 kB)
Collecting sqlparse>=0.3.1 (from django)
  Using cached sqlparse-0.4.4-py3-none-any.whl (41 kB)
Collecting typing-extensions>=4 (from asgiref<4,>=3.6.0->django)
  Obtaining dependency information for typing-extensions>=4 from https://files.pythonhosted.org/packages/24/21/7d397a4b7934ff4028987914ac1044d3b7d52712f30e2ac7a2ae5bc86dd0/typing_extensions-4.8.0-py3-none-any.whl.metadata
  Downloading typing_extensions-4.8.0-py3-none-any.whl.metadata (3.0 kB)
Using cached Django-4.2.5-py3-none-any.whl (8.0 MB)
Using cached asgiref-3.7.2-py3-none-any.whl (24 kB)
Using cached typing_extensions-4.8.0-py3-none-any.whl (31 kB)
Installing collected packages: typing-extensions, sqlparse, asgiref, django
Successfully installed asgiref-3.7.2 django-4.2.5 sqlparse-0.4.4 typing-extensions-4.8.0
```

- [Django REST framework](https://www.django-rest-framework.org/ "Django REST framework")
```
(.venv) ~/Python.projects/cv$ pip install djangorestframework
Collecting djangorestframework
  Using cached djangorestframework-3.14.0-py3-none-any.whl (1.1 MB)
Requirement already satisfied: django>=3.0 in ./.venv/lib/python3.9/site-packages (from djangorestframework) (4.2.5)
Collecting pytz (from djangorestframework)
  Obtaining dependency information for pytz from https://files.pythonhosted.org/packages/32/4d/aaf7eff5deb402fd9a24a1449a8119f00d74ae9c2efa79f8ef9994261fc2/pytz-2023.3.post1-py2.py3-none-any.whl.metadata
  Using cached pytz-2023.3.post1-py2.py3-none-any.whl.metadata (22 kB)
Requirement already satisfied: asgiref<4,>=3.6.0 in ./.venv/lib/python3.9/site-packages (from django>=3.0->djangorestframework) (3.7.2)
Requirement already satisfied: sqlparse>=0.3.1 in ./.venv/lib/python3.9/site-packages (from django>=3.0->djangorestframework) (0.4.4)
Requirement already satisfied: typing-extensions>=4 in ./.venv/lib/python3.9/site-packages (from asgiref<4,>=3.6.0->django>=3.0->djangorestframework) (4.8.0)
Using cached pytz-2023.3.post1-py2.py3-none-any.whl (502 kB)
Installing collected packages: pytz, djangorestframework
Successfully installed djangorestframework-3.14.0 pytz-2023.3.post1
```

- [Pillow](https://pillow.readthedocs.io/en/stable/ "Pillow")
```
(.venv) ~/Python.projects/cv$ pip install Pillow
Collecting Pillow
  Obtaining dependency information for Pillow from https://files.pythonhosted.org/packages/0a/20/a94a0462495de73e248643fb24667270f2e67f44792456ab7207764e80cc/Pillow-10.0.1-cp39-cp39-manylinux_2_28_x86_64.whl.metadata
  Using cached Pillow-10.0.1-cp39-cp39-manylinux_2_28_x86_64.whl.metadata (9.5 kB)
Using cached Pillow-10.0.1-cp39-cp39-manylinux_2_28_x86_64.whl (3.6 MB)
Installing collected packages: Pillow
Successfully installed Pillow-10.0.1
(.venv) ~/Python.projects/cv$ pip install Pillow -U
Requirement already satisfied: Pillow in ./.venv/lib/python3.9/site-packages (10.0.1)
```

- [lxml](https://lxml.de/ "lxml")
```
(.venv) ~/Python.projects/cv$ pip install lxml
Collecting lxml
  Obtaining dependency information for lxml from https://files.pythonhosted.org/packages/c5/a2/7876f76606725340c989b1c73b5501fc41fb21e50a8597c9ecdb63a05b27/lxml-4.9.3-cp39-cp39-manylinux_2_28_x86_64.whl.metadata
  Using cached lxml-4.9.3-cp39-cp39-manylinux_2_28_x86_64.whl.metadata (3.8 kB)
Using cached lxml-4.9.3-cp39-cp39-manylinux_2_28_x86_64.whl (8.0 MB)
Installing collected packages: lxml
Successfully installed lxml-4.9.3
```

- [Beautyfulsoup4](https://www.crummy.com/software/BeautifulSoup/bs4/doc/ "Beautyfulsoup4")
```
(.venv) ~/Python.projects/cv$ pip install beautifulsoup4
Collecting beautifulsoup4
  Using cached beautifulsoup4-4.12.2-py3-none-any.whl (142 kB)
Collecting soupsieve>1.2 (from beautifulsoup4)
  Obtaining dependency information for soupsieve>1.2 from https://files.pythonhosted.org/packages/4c/f3/038b302fdfbe3be7da016777069f26ceefe11a681055ea1f7817546508e3/soupsieve-2.5-py3-none-any.whl.metadata
  Using cached soupsieve-2.5-py3-none-any.whl.metadata (4.7 kB)
Using cached soupsieve-2.5-py3-none-any.whl (36 kB)
Installing collected packages: soupsieve, beautifulsoup4
Successfully installed beautifulsoup4-4.12.2 soupsieve-2.5
```

- [Requests](https://requests.readthedocs.io/en/latest/ "Requests")
```
(.venv) ~/Python.projects/cv$ pip install requests
Collecting requests
  Obtaining dependency information for requests from https://files.pythonhosted.org/packages/70/8e/0e2d847013cb52cd35b38c009bb167a1a26b2ce6cd6965bf26b47bc0bf44/requests-2.31.0-py3-none-any.whl.metadata
  Using cached requests-2.31.0-py3-none-any.whl.metadata (4.6 kB)
Collecting charset-normalizer<4,>=2 (from requests)
  Obtaining dependency information for charset-normalizer<4,>=2 from https://files.pythonhosted.org/packages/f9/0d/514be8597d7a96243e5467a37d337b9399cec117a513fcf9328405d911c0/charset_normalizer-3.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata
  Using cached charset_normalizer-3.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl.metadata (31 kB)
Collecting idna<4,>=2.5 (from requests)
  Using cached idna-3.4-py3-none-any.whl (61 kB)
Collecting urllib3<3,>=1.21.1 (from requests)
  Obtaining dependency information for urllib3<3,>=1.21.1 from https://files.pythonhosted.org/packages/37/dc/399e63f5d1d96bb643404ee830657f4dfcf8503f5ba8fa3c6d465d0c57fe/urllib3-2.0.5-py3-none-any.whl.metadata
  Using cached urllib3-2.0.5-py3-none-any.whl.metadata (6.6 kB)
Collecting certifi>=2017.4.17 (from requests)
  Obtaining dependency information for certifi>=2017.4.17 from https://files.pythonhosted.org/packages/4c/dd/2234eab22353ffc7d94e8d13177aaa050113286e93e7b40eae01fbf7c3d9/certifi-2023.7.22-py3-none-any.whl.metadata
  Using cached certifi-2023.7.22-py3-none-any.whl.metadata (2.2 kB)
Using cached requests-2.31.0-py3-none-any.whl (62 kB)
Using cached certifi-2023.7.22-py3-none-any.whl (158 kB)
Using cached charset_normalizer-3.2.0-cp39-cp39-manylinux_2_17_x86_64.manylinux2014_x86_64.whl (202 kB)
Using cached urllib3-2.0.5-py3-none-any.whl (123 kB)
Installing collected packages: urllib3, idna, charset-normalizer, certifi, requests
Successfully installed certifi-2023.7.22 charset-normalizer-3.2.0 idna-3.4 requests-2.31.0 urllib3-2.0.5
```

# Rights (like license):

At this time, I have not finally decided whether the project will be free for use or not.
At the same time, I know for sure that just as I used the advice and learned the code of others, the code of this project can be useful for beginners. Thus - feel free to use it for educational purposes.

I will consider this project more successful if, using the code or ideas, you include a link to this project in your work.
