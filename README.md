## SciELO Usage

## Dev Installation

To build and run the application, being at the root of the project, you can follow these steps:

1. `make build compose=local.yml`
2. `make django_makemigrations`
3. `make django_migrate`
4. `make django_createsuperuser`
5. `make up`

After the fifth step, the application should be functional and accessible at http://0.0.0.0:8009/admin

### Additional notes:

* The instructions assume that you have a working installation of Docker and `make`.
* The `make` commands use the `compose` file `local.yml` to start the application containers.
* The `django_makemigrations` and `django_migrate` commands are used to create and apply database migrations.
* The `django_createsuperuser` command is used to create a superuser account for the application.
* The `make up` command starts the application containers in the background.
* The application is accessible at http://0.0.0.0:8009/admin.
* To log in to the admin panel, you will need to use the superuser credentials that you created with the `django_createsuperuser` command.
* The `Log Manager` tool can be used to view log files and manage application configurations.
* To test the application, you will need to add some content, such as a list of collections and configurations.
