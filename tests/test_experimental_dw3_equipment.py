"""Experimental DW3 numeric limits retain native storage and dependencies."""
from types import SimpleNamespace
import unittest

from koei_editor.games.dw3 import bodyguard_editor as guards
from koei_editor.games.dw3 import bodyguard_growth as growth
from koei_editor.games.dw3 import officer_weapon_editor as weapons
from koei_editor.games.dw3.models import Change, SaveError
from koei_editor.shared.experimental_limits import experimental_limits


def item_document(*, owned=True, value=1):
    record=[{'name':'GuardEquipItemID','value':guards.GUARD_ITEMS[0]['enum'] if owned else 'EGuardEquipItemID::NUM'},
            {'name':'EquipItemID','value':'EEquipItemID::NUM'},
            {'name':'Value','value':value}]
    return SimpleNamespace(records=lambda name:[record] if name=='GuardEquipItemDataArray' else [])


class ExperimentalDW3EquipmentTests(unittest.TestCase):
    def officer_info(self):
        return {'owned':True,'experimental_existing':True,'array':'WeaponDataArray',
                'weapon_id':6,'blue_limit':6,'blue_minimum':1,
                'skills':[{'id':0,'value':1}]+[{'id':None,'value':0} for _ in range(8)]}

    def test_merit_above_cap_requires_mode_and_keeps_growth_budget(self):
        with self.assertRaises(ValueError):
            growth.budget(100000)
        with experimental_limits():
            self.assertEqual(growth.budget(0x7fffffff),25)
            self.assertEqual(growth.earned_caps(0x7fffffff),growth.LEVEL_CAPS)
            self.assertEqual(growth.safe_preset(0x7fffffff),growth.safe_preset())
            for levels in ([12,0,0,0,0,0],[11,11,11,3,3,3],[0,0,0,4,0,0]):
                with self.subTest(levels=levels), self.assertRaises(ValueError):
                    growth.validate_growth(0x7fffffff,levels)
            for value in (-1,True,100000.0,0x80000000):
                with self.subTest(value=value), self.assertRaises(ValueError):
                    growth.budget(value)
        with self.assertRaises(ValueError):
            growth.budget(100000)

    def test_saved_high_merit_can_be_read_without_authored_mode(self):
        levels=growth.safe_preset()
        self.assertEqual(growth.validate_saved_growth(100000,levels),tuple(levels))
        with self.assertRaises(ValueError):
            growth.validate_growth(100000,levels)

    def test_owned_guard_item_roll_accepts_native_ceiling_only_in_mode(self):
        document=item_document()
        change=Change('guard_item',0,'Value',0x7fffffff)
        with self.assertRaises(SaveError):
            guards.item_state(document,[change])
        with experimental_limits():
            self.assertEqual(guards.item_state(document,[change])[0]['value'],change.value)
            self.assertEqual(guards.max_item_value(document,0),guards.GUARD_ITEMS[0]['max_value'])
            for value in (0,-1,True,40.0,0x80000000):
                with self.subTest(value=value), self.assertRaises(SaveError):
                    guards.item_state(document,[Change('guard_item',0,'Value',value)])

    def test_high_roll_cannot_acquire_an_unowned_guard_item(self):
        with experimental_limits(), self.assertRaises(SaveError):
            guards.item_state(item_document(owned=False,value=0),
                              [Change('guard_item',0,'Owned',True),Change('guard_item',0,'Value',41)])

    def test_guard_bonus_extension_preserves_slot_identity_and_tier_rules(self):
        original=[{'id':0,'value':30}]
        high=[{'id':0,'value':0x7fffffff}]
        with self.assertRaises(SaveError):
            guards.validate_skills(175,high,original)
        with experimental_limits():
            self.assertEqual(guards.validate_skills(175,high,original),high)
            for requested,baseline in ((high,[]),([{'id':1,'value':31}],original),
                                       ([{'id':0,'value':29}],original),
                                       ([{'id':0,'value':0x80000000}],original),
                                       ([{'id':0,'value':True}],original),
                                       ([{'id':4,'value':31}],original)):
                with self.subTest(requested=requested,baseline=baseline), self.assertRaises(SaveError):
                    guards.validate_skills(175,requested,baseline)
            self.assertEqual(guards.max_skills(175),guards.GUARD_WEAPONS[175]['max_bonus_profile'])

    def test_officer_normal_bonus_extension_requires_existing_saved_identity(self):
        info=self.officer_info();skills=[dict(row) for row in info['skills']]
        skills[0]['value']=0x7fffffff
        with self.assertRaises(SaveError):
            weapons.validate_skills(info,skills)
        with experimental_limits():
            self.assertEqual(weapons.validate_skills(info,skills),skills)
            info['experimental_existing']=False
            with self.assertRaises(SaveError):
                weapons.validate_skills(info,skills)
            info['experimental_existing']=True
            skills[0]['id']=1
            with self.assertRaises(SaveError):
                weapons.validate_skills(info,skills)

    def test_officer_storage_rare_slot_and_discrete_bounds_still_apply(self):
        info=self.officer_info()
        with experimental_limits():
            for skill in ({'id':0,'value':0x80000000},{'id':0,'value':True},
                          {'id':0,'value':19},{'id':13,'value':25},
                          {'id':None,'value':25}):
                requested=[dict(row) for row in info['skills']];requested[0]=skill
                with self.subTest(skill=skill), self.assertRaises(SaveError):
                    weapons.validate_skills(info,requested)
            requested=[dict(row) for row in info['skills']]
            requested[0]['value']=25
            requested[1]={'id':0,'value':25}
            with self.assertRaises(SaveError):
                weapons.validate_skills(info,requested)

    def test_high_original_values_preserve_default_readability_and_max(self):
        info=self.officer_info();info['skills'][0]['value']=123456
        self.assertEqual(weapons.validate_skills(info,info['skills']),info['skills'])
        original=[{'id':0,'value':123456}]
        self.assertEqual(guards.validate_skills(175,original,original),original)
        self.assertEqual(guards.max_skills(175,original)[0],original[0])
        self.assertEqual(guards.max_item_value(item_document(value=123456),0),123456)


if __name__=='__main__':
    unittest.main()
