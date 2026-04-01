django.db.backends.postgresql
# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class LekkiEnumeration(models.Model):
    property_id = models.CharField(max_length=200, blank=True, null=True)
    street_name = models.CharField(max_length=150, blank=True, null=True)
    house_number = models.CharField(max_length=20, blank=True, null=True)
    property_type = models.CharField(max_length=50, blank=True, null=True)
    owner_name = models.CharField(max_length=200, blank=True, null=True)
    owner_phone = models.CharField(max_length=20, blank=True, null=True)
    business_type = models.CharField(max_length=100, blank=True, null=True)
    no_of_floors = models.IntegerField(blank=True, null=True)
    no_of_units = models.IntegerField(blank=True, null=True)
    revenue_category = models.CharField(max_length=50, blank=True, null=True)
    photo_front = models.CharField(unique=True, max_length=255, blank=True, null=True)
    photo_gate = models.CharField(unique=True, max_length=255, blank=True, null=True)
    photo_signage = models.CharField(unique=True, max_length=255, blank=True, null=True)
    photo_street = models.CharField(unique=True, max_length=255, blank=True, null=True)
    completeness_status = models.CharField(max_length=20, blank=True, null=True)
    geom = models.TextField(blank=True, null=True)  # This field type is a guess.
    created_at = models.CharField(max_length=50, blank=True, null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    area_in_me = models.FloatField(blank=True, null=True)
    confidence = models.FloatField(blank=True, null=True)
    full_plus_field = models.CharField(db_column='full_plus_', max_length=50, blank=True, null=True)  # Field renamed because it ended with '_'.
    enumeration_date = models.CharField(max_length=50, blank=True, null=True)
    email = models.TextField(blank=True, null=True)
    owner_address = models.CharField(max_length=255, blank=True, null=True)
    contact_name = models.CharField(max_length=200, blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)
    contact_address = models.CharField(max_length=255, blank=True, null=True)
    confirmed_house_number = models.CharField(max_length=20, blank=True, null=True)
    assigned_house_number = models.CharField(max_length=20, blank=True, null=True)
    business_name_1 = models.CharField(max_length=200, blank=True, null=True)
    business_name_2 = models.CharField(max_length=200, blank=True, null=True)
    business_name_3 = models.CharField(max_length=200, blank=True, null=True)
    business_name_4 = models.CharField(max_length=200, blank=True, null=True)
    owner_email = models.CharField(max_length=100, blank=True, null=True)
    contact_email = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'lekki_enumeration'
