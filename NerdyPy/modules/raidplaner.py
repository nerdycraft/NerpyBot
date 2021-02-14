from datetime import datetime
from enum import Enum

from discord import Embed
from discord.ext.commands import Cog, command

from models.RaidEncounter import RaidEncounter
from models.RaidEncounterRole import RaidEncounterRole
from models.RaidTemplate import RaidTemplate
from utils.conversation import Conversation


class RaidPlaner(Cog):
    """cog for administrative usage"""

    def __init__(self, bot):
        bot.log.info(f"loaded {__name__}")

        self.bot = bot

    @command()
    async def raidplaner(self, ctx):
        """sound and text tags"""
        await self.bot.convMan.init_conversation(RaidConversation(self.bot, ctx.author, ctx.guild))


class RaidPlanerState(Enum):
    MAIN_MENU = 0

    TEMPLATE_MENU = 101
    TEMPLATE_ADD = 102
    TEMPLATE_EDIT = 103
    TEMPLATE_REMOVE = 110
    TEMPLATE_REMOVE_CONFIRM = 111
    TEMPLATE_REMOVE_SAVE = 112
    TEMPLATE_NAME = 140
    TEMPLATE_DESC = 141
    TEMPLATE_COUNT = 142
    TEMPLATE_PREVIEW = 160
    TEMPLATE_SAVE = 199

    TEMPLATE_ENCOUNTER_MENU = 201
    TEMPLATE_ENCOUNTER_ADD = 202
    TEMPLATE_ENCOUNTER_EDIT = 203
    TEMPLATE_ENCOUNTER_REMOVE = 211
    TEMPLATE_ENCOUNTER_REMOVE_CONFIRM = 212
    TEMPLATE_ENCOUNTER_REMOVE_SAVE = 213
    TEMPLATE_ENCOUNTER_NAME = 240
    TEMPLATE_ENCOUNTER_DESC = 241
    TEMPLATE_ENCOUNTER_SAVE = 299

    TEMPLATE_ENCOUNTER_ROLE_ADD = 301
    TEMPLATE_ENCOUNTER_ROLE_ADD_DESC = 302
    TEMPLATE_ENCOUNTER_ROLE_ADD_COUNT = 303
    TEMPLATE_ENCOUNTER_ROLE_ADD_SORT = 304
    TEMPLATE_ENCOUNTER_ROLE_EDIT = 321
    TEMPLATE_ENCOUNTER_ROLE_EDIT_NAME = 322
    TEMPLATE_ENCOUNTER_ROLE_EDIT_DESC = 323
    TEMPLATE_ENCOUNTER_ROLE_EDIT_COUNT = 324
    TEMPLATE_ENCOUNTER_ROLE_EDIT_SORT = 325
    TEMPLATE_ENCOUNTER_ROLE_REMOVE = 340
    TEMPLATE_ENCOUNTER_ROLE_REMOVE_CONFIRM = 341
    TEMPLATE_ENCOUNTER_ROLE_REMOVE_SAVE = 342
    TEMPLATE_ENCOUNTER_ROLE_SAVE = 399

    EVENT = 500
    EVENT_EDIT = 600

    CLOSE = 999

# TODO: data validation


class RaidConversation(Conversation):

    # noinspection PyTypeChecker
    def __init__(self, bot, user, guild):
        super().__init__(bot, user, guild)
        self.tmpTemplate: RaidTemplate = None
        self.tmpEncounter: RaidEncounter = None
        self.tmpRole: RaidEncounterRole = None

        with self.bot.session_scope() as session:
            self.templates = RaidTemplate.get_from_guild(guild.id, session)

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
            RaidPlanerState.TEMPLATE_COUNT: self.conv_template_set_count,

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
            RaidPlanerState.EVENT: self.use_template,
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
                    description=f'Template \'{self.tmpTemplate.Name}\' in the works. It is currently designed for '
                                f'{self.tmpTemplate.get_required_participants()}🧑‍🤝‍🧑 players and has '
                                f'{self.tmpTemplate.get_encounter_count()} encounters.'
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
            '⏩': RaidPlanerState.TEMPLATE_COUNT,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_COUNT, self.set_template_desc, reactions)

    async def conv_template_set_count(self):
        emb = Embed(title='RaidPlaner',
                    description='For how many players is this event designed?'
                    )

        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_MENU, self.set_template_count, reactions)

    async def conv_template_create(self):
        self.tmpTemplate = RaidTemplate(
            GuildId=self.guild.id,
            RaidId=len(self.templates) + 1,
            Name=f'RaidTemplate {len(self.templates) + 1}',
            PlayerCount=10,
            CreateDate=datetime.utcnow()
        )
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
            emb.description += f'**{i + 1}:** {self.templates[i].Name}\n'

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
            emb.description += f'**{i}:** {self.templates[i].Name}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.MAIN_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_REMOVE_CONFIRM, self.set_edit_template, reactions)

    async def conv_template_remove_confirm(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Do your really want to remove template {self.tmpTemplate.Name}?'
                    )

        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_REMOVE_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.MAIN_MENU,
        }
        await self.send_react(emb, reactions)

    async def conv_template_remove_save(self):
        with self.bot.session_scope() as session:
            session.delete(self.tmpTemplate)
        await self.conv_main_menu()

    async def conv_template_save(self):
        with self.bot.session_scope() as session:
            session.add(self.tmpTemplate)

        await self.conv_main_menu()

    async def set_template_name(self, answer):
        if len(answer) > 10:
            emb = Embed(title='RaidPlaner',
                        description='Name can not be longer than 10 characters'
                        )
            await self.send_ns(emb)
            return False
        self.tmpTemplate.Name = answer

    async def set_template_desc(self, answer):
        self.tmpTemplate.Description = answer

    async def set_template_count(self, answer):
        self.tmpTemplate.PlayerCount = int(answer)

    async def set_edit_template(self, answer):
        self.tmpTemplate = self.templates[int(answer) - 1]
    # endregion

    # region encounter
    async def conv_encounter_menu(self):
        emb = Embed(title='RaidPlaner',
                    description='Designing an encounter. The number of selectable roles defines the number selectable'
                                'roles needed on following encounters. Currently your encounter looks like this:'
                                '\n\n'
                                f'{self.tmpEncounter.info()}'
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
        self.tmpEncounter = RaidEncounter(
            GuildId=self.guild.id,
            RaidId=self.tmpTemplate.RaidId,
            EncounterId=self.tmpTemplate.get_encounter_count() + 1,
            Name=f'Encounter {self.tmpTemplate.get_encounter_count() + 1}'
        )
        self.tmpEncounter.isNew = True
        await self.conv_encounter_menu()

    async def conv_encounter_select(self):
        encounter_count = self.tmpTemplate.get_encounter_count()
        if encounter_count == 0:
            return await self.conv_encounter_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing a encounter below:'
                                '\n\n'
                    )

        for i in range(encounter_count):
            emb.description += f'**{i + 1}:** {self.tmpTemplate.Encounters[i].Name}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_MENU, self.set_edit_encounter, reactions)

    async def conv_encounter_remove(self):
        encounter_count = self.tmpTemplate.get_encounter_count()
        if encounter_count == 0:
            return await self.conv_template_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing an encounter below:'
                                '\n\n'
                    )

        for i in range(encounter_count):
            emb.description += f'**{i + 1}:** {self.tmpTemplate.Encounters[i].Name}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE_CONFIRM, self.set_edit_encounter, reactions)

    async def conv_encounter_remove_confirm(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Do your really want to remove encounter {self.tmpEncounter.Name}?'
                    )

        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_react(emb, reactions)

    async def conv_encounter_remove_save(self):
        self.tmpTemplate.Encounters.remove(self.tmpEncounter)
        await self.conv_template_menu()

    async def conv_encounter_name(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Give your Encounter a new name. Currently it\'s {self.tmpEncounter.Name}.'
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
        if self.tmpEncounter.isNew is True:
            self.tmpTemplate.Encounters.append(self.tmpEncounter)
            self.tmpEncounter.isNew = False
        await self.conv_template_menu()

    async def set_encounter_name(self, answer):
        if len(answer) > 10:
            emb = Embed(title='RaidPlaner',
                        description='Name can not be longer than 10 characters'
                        )
            await self.send_ns(emb)
            return False
        self.tmpEncounter.Name = answer

    async def set_encounter_desc(self, answer):
        self.tmpEncounter.Description = answer

    async def set_edit_encounter(self, answer):
        self.tmpEncounter = self.tmpTemplate.Encounters[int(answer) - 1]
        self.tmpEncounter.Roles.sort(key=lambda r: r.SortIndex)
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
        role_count = self.tmpEncounter.get_role_count()
        if role_count == 0:
            return await self.conv_encounter_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing a role below:'
                                '\n\n'
                    )

        for i in range(role_count):
            emb.description += f'**{i + 1}:** {self.tmpEncounter.Roles[i]}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_NAME, self.set_edit_role, reactions)

    async def conv_role_edit_name(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Give your role "{self.tmpRole.Name}" a new name. Remember: First character must be '
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
                                f'*{self.tmpRole.Description}*'
                    )

        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_COUNT,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_COUNT, self.set_role_desc, reactions)

    async def conv_role_edit_count(self):
        emb = Embed(title='RaidPlaner',
                    description=f'How many players can apply for this role. Currently it\'s {self.tmpRole.Count}.'
                    )
        reactions = {
            '⏩': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_SORT,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_SORT, self.set_role_count, reactions)

    async def conv_role_edit_sort(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Set the sort index for the role. Currently it\'s {self.tmpRole.SortIndex}.'
                    )
        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_SAVE, self.set_role_sort, reactions)

    async def conv_role_save(self):
        if self.tmpRole.isNew is True:
            self.tmpEncounter.Roles.append(self.tmpRole)
            self.tmpRole.isNew = False
        self.tmpEncounter.Roles.sort(key=lambda r: r.SortIndex)
        await self.conv_encounter_menu()

    async def conv_remove_role(self):
        role_count = self.tmpEncounter.get_role_count()
        if role_count == 0:
            return await self.conv_encounter_menu()

        emb = Embed(title='RaidPlaner',
                    description='Type in the number referencing a role below:'
                                '\n\n'
                    )

        for i in range(role_count):
            emb.description += f'**{i}:** {self.tmpEncounter.Roles[i]}\n'

        reactions = {
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE_CONFIRM, self.set_edit_role, reactions)

    async def conv_remove_role_confirm(self):
        emb = Embed(title='RaidPlaner',
                    description=f'Do your really want to remove role {self.tmpRole.Name}?'
                    )

        reactions = {
            '<:check:809765339230896128>': RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE_SAVE,
            '<:cancel:809790666930126888>': RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_react(emb, reactions)

    async def conv_remove_role_save(self):
        self.tmpEncounter.Roles.remove(self.tmpRole)
        self.tmpEncounter.Roles.sort(key=lambda r: r.SortIndex)
        await self.conv_encounter_menu()

    async def create_new_role(self, answer):
        self.tmpRole = RaidEncounterRole(
            GuildId=self.guild.id,
            RaidId=self.tmpEncounter.RaidId,
            EncounterId=self.tmpEncounter.EncounterId,
        )
        if await self.set_role_name(answer) is not None:
            return False

    async def set_role_name(self, answer):
        self.tmpRole.Name = answer

    async def set_role_desc(self, answer):
        self.tmpRole.Description = answer

    async def set_role_count(self, answer):
        self.tmpRole.Count = int(answer)

    async def set_role_sort(self, answer):
        self.tmpRole.SortIndex = int(answer)

    async def set_edit_role(self, answer):
        self.tmpRole = self.tmpEncounter.Roles[int(answer) - 1]
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
