class ScorerRouter:
    data_model_app_labels = {"data_model"}
    data_model_db = "data_model"

    def db_for_read(self, model, **hints):
        """
        Attempts to read data_model from the data_model db.
        """
        if model._meta.app_label in self.data_model_app_labels:
            return self.data_model_db
        return None

    def db_for_write(self, model, **hints):
        """
        Attempts to read data_model from the data_model db.
        """
        if model._meta.app_label in self.data_model_app_labels:
            return self.data_model_db
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        We have no oppinion, but we expect the data_model app to have no relations to other apps.
        """
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Migrations for the data_model app run only on the data_model DB,
        and migrations for every other app run only on the default DB.
        """
        if app_label in self.data_model_app_labels:
            return db == self.data_model_db
        return db == "default"
