from copy import copy, deepcopy
from enum import Enum
from typing import List

from discord import Embed
from discord.ext.commands import Cog, command

from utils.conversation import Conversation


class RaidPlaner(Cog):
    """cog for administrative usage"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

    @command()
    async def raidplaner(self, ctx):
        """sound and text tags"""
        await self.bot.convMan.init_conversation(RaidConversation(ctx.author, ctx.guild))


class EncounterRole:

    def __init__(self):
        self.icon = ""
        self.name = ""
        self.desc = ""
        self.count = 0
        self.sortIndex = 0

    def __str__(self):
        return f'{self.icon} ***{self.name}*** ({self.count})\n{self.desc}'


class EncounterTemplate:

    def __init__(self, name):
        self.name = name
        self.desc = ""
        self.roles: List[EncounterRole] = []

    def get_total_participants(self):
        return sum(r.count for r in self.roles)

    def __str__(self):
        to_str = f'**{self.name}** (🧑‍🤝‍🧑{self.get_total_participants()})\n\n'
        for role in self.roles:
            to_str += f'{role}\n\n'
        return to_str


class RaidTemplate:

    def __init__(self):
        self.name = "CoolTemplateName"
        self.desc = "Best template in town."
        self.encounters: List[EncounterTemplate] = []

    def add_encounter(self, encounter: EncounterTemplate):
        self.encounters.append(encounter)

    def get_required_participants(self):
        if len(self.encounters) == 0:
            return 0
        return self.encounters[0].get_total_participants()

    def create_embed(self):
        emb = Embed(title=self.name,
                    description=f'{self.desc}\n'
                                f'🧑‍🤝‍🧑{self.get_required_participants()}\n\n'
                    )

        for enc in self.encounters:
            emb.description += str(enc)

        return emb


class RaidPlanerState(Enum):
    MAIN_MENU = 0

    TEMPLATE_MENU = 1
    TEMPLATE_ADD = 2
    TEMPLATE_EDIT = 3
    TEMPLATE_REMOVE = 4
    TEMPLATE_REMOVE_CONFIRM = 5
    TEMPLATE_REMOVE_SAVE = 6
    TEMPLATE_NAME = 7
    TEMPLATE_DESC = 8
    TEMPLATE_SAVE = 9

    TEMPLATE_ENCOUNTER_MENU = 10
    TEMPLATE_ENCOUNTER_ADD = 11
    TEMPLATE_ENCOUNTER_EDIT = 12
    TEMPLATE_ENCOUNTER_REMOVE = 13
    TEMPLATE_ENCOUNTER_REMOVE_CONFIRM = 14
    TEMPLATE_ENCOUNTER_REMOVE_SAVE = 15
    TEMPLATE_ENCOUNTER_NAME = 16
    TEMPLATE_ENCOUNTER_DESC = 17
    TEMPLATE_ENCOUNTER_SAVE = 19

    TEMPLATE_ENCOUNTER_ROLE_ADD = 25
    TEMPLATE_ENCOUNTER_ROLE_ADD_DESC = 26
    TEMPLATE_ENCOUNTER_ROLE_ADD_COUNT = 27
    TEMPLATE_ENCOUNTER_ROLE_ADD_SORT = 28
    TEMPLATE_ENCOUNTER_ROLE_EDIT = 30
    TEMPLATE_ENCOUNTER_ROLE_EDIT_NAME = 31
    TEMPLATE_ENCOUNTER_ROLE_EDIT_DESC = 32
    TEMPLATE_ENCOUNTER_ROLE_EDIT_COUNT = 33
    TEMPLATE_ENCOUNTER_ROLE_EDIT_SORT = 34
    TEMPLATE_ENCOUNTER_ROLE_REMOVE = 36
    TEMPLATE_ENCOUNTER_ROLE_REMOVE_CONFIRM = 37
    TEMPLATE_ENCOUNTER_ROLE_REMOVE_SAVE = 38
    TEMPLATE_ENCOUNTER_ROLE_SAVE = 39

    TEMPLATE_PREVIEW = 50

    EVENT = 100
    EVENT_EDIT = 150

    CLOSE = 999


class RaidConversation(Conversation):

    def __init__(self, user, guild):
        super().__init__(user, guild)
        self.tmpTemplate: RaidTemplate = None
        self.tmpEncounter: EncounterTemplate = None
        self.tmpRole: EncounterRole = None

        self.editTemplateIdx = -1
        self.editEncounterIdx = -1
        self.editRoleIdx = -1

        #  aus db
        self.templates: List[RaidTemplate] = []

    def create_state_handler(self):
        return {
            RaidPlanerState.MAIN_MENU: self.conv_main_menu,

            RaidPlanerState.TEMPLATE_MENU: self.conv_template_menu,
            RaidPlanerState.TEMPLATE_ADD: self.conv_template_create,
            RaidPlanerState.TEMPLATE_EDIT: self.conv_template_select,
            RaidPlanerState.TEMPLATE_REMOVE: self.conv_template_remove,
            RaidPlanerState.TEMPLATE_REMOVE_CONFIRM: self.conv_template_remove_confirm,
            RaidPlanerState.TEMPLATE_REMOVE_SAVE: self.conv_template_remove_save,

            RaidPlanerState.TEMPLATE_NAME: self.conv_template_set_name,
            RaidPlanerState.TEMPLATE_DESC: self.conv_template_set_desc,

            RaidPlanerState.TEMPLATE_SAVE: self.conv_template_save,

            RaidPlanerState.TEMPLATE_ENCOUNTER_MENU: self.conv_encounter_menu,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ADD: self.conv_encounter_add,
            RaidPlanerState.TEMPLATE_ENCOUNTER_EDIT: self.conv_encounter_select,
            RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE: self.conv_encounter_remove,
            RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE_CONFIRM: self.conv_encounter_remove_confirm,
            RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE_SAVE: self.conv_encounter_remove_save,

            RaidPlanerState.TEMPLATE_ENCOUNTER_NAME: self.conv_encounter_name,
            RaidPlanerState.TEMPLATE_ENCOUNTER_DESC: self.conv_encounter_desc,

            RaidPlanerState.TEMPLATE_ENCOUNTER_SAVE: self.conv_encounter_save,

            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD: self.conv_role_add,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_DESC: self.conv_role_add_desc,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_COUNT: self.conv_role_add_count,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_SORT: self.conv_role_add_sort,

            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT: self.conv_role_edit_select,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_NAME: self.conv_role_edit_name,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_DESC: self.conv_role_edit_desc,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_COUNT: self.conv_role_edit_count,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_SORT: self.conv_role_edit_sort,

            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_SAVE: self.conv_role_save,

            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE: self.conv_remove_role,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE_CONFIRM: self.conv_remove_role_confirm,
            RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE_SAVE: self.conv_remove_role_save,

            RaidPlanerState.TEMPLATE_PREVIEW: self.create_template_preview,
            RaidPlanerState.SCHEDULE_EVENT: self.use_template,
            RaidPlanerState.CLOSE: self.close
        }

    async def conv_main_menu(self):
        emb = Embed(title='RaidPlaner',
                    description='Hey there,\n'
                                'this is NerdyBot with your raid planning tool. Just follow the path by responding '
                                'via the reaction presets or with chat input. Now, what would you like to do?\n\n'
                                '<:check:809765339230896128>: schedule event\n'
                                '--------------------------------------------\n'
                                '<:add:809765525629698088>: create a new template\n'
                                '<:edit:809884574497898557>: edit an existing template\n'
                                '<:remove:809885458220974100>: remove an existing template\n'
                                '--------------------------------------------\n'
                                '<:cancel:809790666930126888>: cancel conversation'
                    )

        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.EVENT,
            '<:edit2:810114710938189874>': RaidPlanerState.EVENT_EDIT,
            '<:add:809765525629698088>': RaidPlanerState.TEMPLATE_ADD,
            '<:edit:809884574497898557>': RaidPlanerState.TEMPLATE_EDIT,
            '<:remove:809885458220974100>': RaidPlanerState.TEMPLATE_REMOVE,
            '<:cancel:809790666930126888>': RaidPlanerState.CLOSE,
        }

        await self.send_react(emb, reactions)

    # region template
    async def conv_template_menu(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Template \'{self.tmpTemplate.name}\' in the works. It is currently designed for '
                                f'🧑‍🤝‍🧑{self.tmpTemplate.get_required_participants()} players and has '
                                f'{len(self.tmpTemplate.encounters)} encounters.'
                                '\n\n'
                                '<:edit2:810114710938189874>: change name and description\n'
                                '<:add:809765525629698088>: add encounter\n'
                                '<:edit:809884574497898557>: edit encounter\n'
                                '<:remove:809885458220974100>: remove encounter\n'
                                '<:preview:810222989450543116>: preview template\n'
                                '<:check:809765339230896128>: save template\n'
                                '<:cancel:809790666930126888>: cancel'
                    )

        reactions = {
            '<:edit2:810114710938189874>': RaidPlanerState.TEMPLATE_NAME,
            '<:add:809765525629698088>': RaidPlanerState.TEMPLATE_ENCOUNTER_ADD,
            '<:edit:809884574497898557>': RaidPlanerState.TEMPLATE_ENCOUNTER_EDIT,
            '<:remove:809885458220974100>': RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE,
            '<:preview:810222989450543116>': RaidPlanerState.TEMPLATE_PREVIEW,
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.MAIN_MENU,
        }

        await self.send_react(emb, reactions)

    async def conv_template_set_name(self):
        emb = Embed(title='RaidPlaner',
                    description='To create a new template you first need to give it a name. Just type it in the chat.'
                    )

        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_DESC,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_DESC, self.set_template_name, reactions)

    async def conv_template_set_desc(self):
        emb = Embed(title='RaidPlaner',
                    description='Write a few lines to describe your event.'
                    )

        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_MENU, self.set_template_desc, reactions)

    async def conv_template_create(self):
        self.editTemplateIdx = -1
        self.tmpTemplate = RaidTemplate()
        await self.conv_template_menu()

    async def conv_template_select(self):
        template_count = len(self.templates)
        if template_count == 0:
            return await self.conv_main_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing a template below:'
                                '\n\n'
                    )

        for i in range(template_count):
            emb.description += f'**{i + 1}:** {self.templates[i].name}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.MAIN_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_MENU, self.set_edit_template, reactions)

    async def conv_template_remove(self):
        template_count = len(self.templates)
        if template_count == 0:
            return await self.conv_template_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing a template below:'
                                '\n\n'
                    )

        for i in range(template_count):
            emb.description += f'**{i}:** {self.templates[i]}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.MAIN_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_REMOVE_CONFIRM, self.set_edit_template, reactions)

    async def conv_template_remove_confirm(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Do your really want to remove template {self.tmpTemplate.name}?'
                    )

        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_REMOVE_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.MAIN_MENU,
        }
        await self.send_react(emb, reactions)

    async def conv_template_remove_save(self):
        self.templates.pop(self.editTemplateIdx)
        await self.conv_main_menu()

    async def conv_template_save(self):
        if self.editTemplateIdx < 0:
            self.templates.append(self.tmpTemplate)
        else:
            self.templates[self.editTemplateIdx] = self.tmpTemplate
        await self.conv_main_menu()

    async def set_template_name(self, answer):
        if len(answer) > 10:
            emb = Embed(title='RaidPlaner',
                        description='Name can not be longer than 10 characters'
                        )
            await self.send_ns(emb)
            return False
        self.tmpTemplate.name = answer

    async def set_template_desc(self, answer):
        self.tmpTemplate.desc = answer

    async def set_edit_template(self, answer):
        self.editTemplateIdx = int(answer) - 1
        self.tmpTemplate = deepcopy(self.templates[self.editTemplateIdx])
    # endregion

    # region encounter
    async def conv_encounter_menu(self):
        emb = Embed(title='RaidPlaner',
                    description='Designing an encounter. The number of selectable roles defines the number selectable'
                                'roles needed on following encounters. Currently your encounter looks like this:'
                                '\n\n'
                                f'{self.tmpEncounter}'
                                '\n\n'
                                '<:edit2:810114710938189874>: change name an description\n'
                                '<:add:809765525629698088>: add new role\n'
                                '<:edit:809884574497898557>: edit an existing role\n'
                                '<:remove:809885458220974100>: remove an existing role\n'
                                '<:check:809765339230896128>: finish encounter\n'
                                '<:cancel:809790666930126888>: cancel encounter creation\n'
                    )

        reactions = {
            '<:edit2:810114710938189874>': RaidPlanerState.TEMPLATE_ENCOUNTER_NAME,
            '<:add:809765525629698088>': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD,
            '<:edit:809884574497898557>': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT,
            '<:remove:809885458220974100>': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE,
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_ENCOUNTER_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_MENU,
        }

        await self.send_react(emb, reactions)

    async def conv_encounter_add(self):
        self.editEncounterIdx = -1
        self.tmpEncounter = EncounterTemplate(f'Encounter {len(self.tmpTemplate.encounters) + 1}')
        await self.conv_encounter_menu()

    async def conv_encounter_select(self):
        encounter_count = len(self.tmpTemplate.encounters)
        if encounter_count == 0:
            return await self.conv_encounter_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing a encounter below:'
                                '\n\n'
                    )

        for i in range(encounter_count):
            emb.description += f'**{i + 1}:** {self.tmpTemplate.encounters[i].name}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_MENU, self.set_edit_encounter, reactions)

    async def conv_encounter_remove(self):
        encounter_count = len(self.tmpTemplate.encounters)
        if encounter_count == 0:
            return await self.conv_template_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing an encounter below:'
                                '\n\n'
                    )

        for i in range(encounter_count):
            emb.description += f'**{i}:** {self.tmpTemplate.encounters[i]}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE_CONFIRM, self.set_edit_encounter, reactions)

    async def conv_encounter_remove_confirm(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Do your really want to remove encounter {self.tmpEncounter.name}?'
                    )

        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_react(emb, reactions)

    async def conv_encounter_remove_save(self):
        self.tmpTemplate.encounters.pop(self.editEncounterIdx)
        await self.conv_template_menu()

    async def conv_encounter_name(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Give your Encounter a new name. Currently it\'s {self.tmpEncounter.name}.'
                    )

        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_ENCOUNTER_DESC,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_DESC, self.set_encounter_name, reactions)

    async def conv_encounter_desc(self):
        emb = Embed(title='RaidPlaner',
                    description='Write a few lines to describe your encounter.'
                    )

        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_MENU, self.set_encounter_desc, reactions)

    async def conv_encounter_save(self):
        if self.editEncounterIdx < 0:
            self.tmpTemplate.encounters.append(self.tmpEncounter)
        else:
            self.tmpTemplate.encounters[self.editEncounterIdx] = self.tmpEncounter
        await self.conv_template_menu()

    async def set_encounter_name(self, answer):
        if len(answer) > 10:
            emb = Embed(title='RaidPlaner',
                        description='Name can not be longer than 10 characters'
                        )
            await self.send_ns(emb)
            return False
        self.tmpEncounter.name = answer

    async def set_encounter_desc(self, answer):
        self.tmpEncounter.desc = answer

    async def set_edit_encounter(self, answer):
        self.editEncounterIdx = int(answer) - 1
        self.tmpEncounter = deepcopy(self.tmpTemplate.encounters[self.editTemplateIdx])
    # endregion

    # region role
    async def conv_role_add(self):
        emb = Embed(title='RaidPlaner',
                    description='Name the role you would like to add. First character must be an emoji!'
                    )
        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_DESC, self.create_new_role, reactions)

    async def conv_role_add_desc(self):
        emb = Embed(title='RaidPlaner',
                    description='Add a short description to your role.'
                    )

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_COUNT, self.set_role_desc, reactions)

    async def conv_role_add_count(self):
        emb = Embed(title='RaidPlaner',
                    description='How many players can apply for this role.'
                    )
        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_SORT, self.set_role_count, reactions)

    async def conv_role_add_sort(self):
        emb = Embed(title='RaidPlaner',
                    description='Set the index by which the role should be sorted.'
                    )
        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_SAVE, self.set_role_sort, reactions)

    async def conv_role_edit_select(self):
        role_count = len(self.tmpEncounter.roles)
        if role_count == 0:
            return await self.conv_encounter_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing a role below:'
                                '\n\n'
                    )

        for i in range(role_count):
            emb.description += f'**{i + 1}:** {self.tmpEncounter.roles[i]}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_NAME, self.set_edit_role, reactions)

    async def conv_role_edit_name(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Give your role "{self.tmpRole.name}" a new name. Remember: First character must be '
                                f'an emoji!'
                    )
        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_DESC,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_DESC, self.set_role_name, reactions)

    async def conv_role_edit_desc(self):
        emb = Embed(title='RaidPlaner',
                    description='Give your role a new description. Your current description:\n'
                                f'*{self.tmpRole.desc}*'
                    )

        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_COUNT,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_COUNT, self.set_role_desc, reactions)

    async def conv_role_edit_count(self):
        emb = Embed(title='RaidPlaner',
                    description=f'How many players can apply for this role. Currently it\'s {self.tmpRole.count}.'
                    )
        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_SORT,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_SORT, self.set_role_count, reactions)

    async def conv_role_edit_sort(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Set the sort index for the role. Currently it\'s {self.tmpRole.sortIndex}.'
                    )
        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_SAVE, self.set_role_sort, reactions)

    async def conv_role_save(self):
        if self.editRoleIdx < 0:
            self.tmpEncounter.roles.append(self.tmpRole)
        else:
            self.tmpEncounter.roles[self.editRoleIdx] = self.tmpRole
        self.tmpEncounter.roles.sort(key=lambda r: r.sortIndex)
        self.editRoleIdx = -1
        await self.conv_encounter_menu()

    async def conv_remove_role(self):
        role_count = len(self.tmpEncounter.roles)
        if role_count == 0:
            return await self.conv_encounter_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing a role below:'
                                '\n\n'
                    )

        for i in range(role_count):
            emb.description += f'**{i}:** {self.tmpEncounter.roles[i]}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE_CONFIRM, self.set_edit_role, reactions)

    async def conv_remove_role_confirm(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Do your really want to remove role {self.tmpRole.name}?'
                    )

        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_react(emb, reactions)

    async def conv_remove_role_save(self):
        self.tmpEncounter.roles.pop(self.editRoleIdx)
        self.tmpEncounter.roles.sort(key=lambda r: r.sortIndex)
        await self.conv_encounter_menu()

    async def create_new_role(self, answer):
        self.tmpRole = EncounterRole()
        if await self.set_role_name(answer) is not None:
            return False

    async def set_role_name(self, answer):
        self.tmpRole.name = answer

    async def set_role_desc(self, answer):
        self.tmpRole.desc = answer

    async def set_role_count(self, answer):
        self.tmpRole.count = int(answer)

    async def set_role_sort(self, answer):
        self.tmpRole.sortIndex = int(answer)

    async def set_edit_role(self, answer):
        self.editRoleIdx = int(answer) - 1
        self.tmpRole = copy(self.tmpEncounter.roles[self.editRoleIdx])
    # endregion

    async def create_template_preview(self):
        await self.send_ns(embed=self.tmpTemplate.create_embed())
        emb = Embed(title='RaidPlaner',
                    description='Above you can see the preview. Looking good eh?'
                    )

        reactions = {
            '👍': RaidPlanerState.MAIN_MENU,
        }
        await self.send_react(emb, reactions)

    async def use_template(self):
        emb = Embed(title='RaidPlaner', description='use_template PoC message (send text to continue)')
        await self.send_msg(emb, RaidPlanerState.MAIN_MENU)


def setup(bot):
    """adds this module to the bot"""
    bot.add_cog(RaidPlaner(bot))
