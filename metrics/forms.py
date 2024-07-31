from wagtail.admin.forms import WagtailAdminModelForm


class Top100ArticlesFileForm(WagtailAdminModelForm):
    def save_all(self, user):
        top100_articles_file = super().save(commit=False)

        if self.instance.pk is not None:
            top100_articles_file.updated_by = user
        else:
            top100_articles_file.creator = user

        self.save()

        return top100_articles_file
