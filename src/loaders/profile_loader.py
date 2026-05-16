class ProfileLoader:
    def __init__(self, profile):
        self.profile = profile or {}

    def get_self_first(self):
        return self.profile.get("self_first_name", "") or ""

    def get_self_last(self):
        return self.profile.get("self_last_name", "") or ""

    def get_partner_first(self):
        return self.profile.get("partner_first_name", "") or ""

    def get_partner_last(self):
        return self.profile.get("partner_last_name", "") or ""

    def get_children_first(self):
        names = []
        for child in self.profile.get("children", []):
            if not isinstance(child, dict) or not child.get("first_name"):
                continue
            first_name = child.get("first_name")
            if isinstance(first_name, list):
                names.extend(name for name in first_name if name)
            else:
                names.append(first_name)
        return names

    def get_children_last(self):
        names = []
        for child in self.profile.get("children", []):
            if not isinstance(child, dict) or not child.get("last_name"):
                continue
            last_name = child.get("last_name")
            if isinstance(last_name, list):
                names.extend(name for name in last_name if name)
            else:
                names.append(last_name)
        return names

    def get_children(self):
        children = self.profile.get("children", [])
        return children if isinstance(children, list) else []

    def get_pets(self):
        pets = self.profile.get("pets", [])
        return pets if isinstance(pets, list) else []

    def get_region(self):
        return self.profile.get("region", "") or ""

    def get_nationality(self):
        return self.profile.get("nationality", "") or ""

    def get_interests(self):
        interests = self.profile.get("interests", [])
        return interests if isinstance(interests, list) else []

    def get_company(self):
        return self.profile.get("company", "") or ""

    def get_birth_date(self):
        return self.profile.get("birth_date", "") or ""

    def get_age(self):
        return self.profile.get("age")

    def get_previous_passwords(self):
        passwords = self.profile.get("previous_passwords", []) or []
        return passwords if isinstance(passwords, list) else []

    def get_car_brand(self):
        return self.profile.get("car_brand", "") or ""
