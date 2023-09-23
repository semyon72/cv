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

# What the project has and no in short

## What the project has:
    - Implemented the ready to use DB structure
    - RESTful API with login through session authentication (Ajax)
    - For simplification, SQLite was used

## What the project has no:
    - Any implemented representations
    - Any UI
    - Sign Up user (you can create a user using Django Admin or manually in code using a model)

# Rights (like license):

At this time, I have not finally decided whether the project will be free for use or not.
At the same time, I know for sure that just as I used the advice and learned the code of others, the code of this project can be useful for beginners. Thus - feel free to use it for educational purposes.

I will consider this project more successful if, using the code or ideas, you include a link to this project in your work.
