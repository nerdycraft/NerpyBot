from datetime import datetime
from enum import Enum

from discord import Embed
from discord.ext.commands import Cog, command

from models.RaidEncounter import RaidEncounter
from models.RaidEncounterRole import RaidEncounterRole
from models.RaidEvent import RaidEvent
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
        conv = RaidConversation(self.bot, ctx.author, self.bot.get_guild(606539392311361794))
        await self.bot.convMan.init_conversation(conv)


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

    EVENT_CREATE = 500
    EVENT_CREATE_TEMPLATE = 501
    EVENT_CREATE_NAME = 502
    EVENT_CREATE_DESC = 503
    EVENT_CREATE_START = 504
    EVENT_CREATE_END = 505
    EVENT_CREATE_CHANNEL = 506
    EVENT_CREATE_PREVIEW = 509
    EVENT_EDIT = 600

    CLOSE = 999


# TODO: emoji check for roles


class RaidConversation(Conversation):

    # noinspection PyTypeChecker
    def __init__(self, bot, user, guild):
        super().__init__(bot, user, guild)

        self.templates = []

        self.tmpTemplate: RaidTemplate = None
        self.tmpEncounter: RaidEncounter = None
        self.tmpRole: RaidEncounterRole = None

        self.tmpEvent: RaidEvent = None

        self.refresh_data()

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
            RaidPlanerState.EVENT_CREATE: self.conv_create_event,
            RaidPlanerState.EVENT_CREATE_TEMPLATE: self.conv_create_event_template,
            RaidPlanerState.EVENT_CREATE_NAME: self.conv_create_event_name,
            RaidPlanerState.EVENT_CREATE_DESC: self.conv_create_event_desc,
            RaidPlanerState.EVENT_CREATE_START: self.conv_create_event_template,
            RaidPlanerState.EVENT_CREATE_END: self.conv_create_event_template,
            RaidPlanerState.EVENT_CREATE_CHANNEL: self.conv_create_event_template,
            RaidPlanerState.CLOSE: self.close,
        }

    async def conv_main_menu(self):
        self.refresh_data()
        emb = Embed(
            title="RaidPlaner",
            description="Hey there,\n"
            "this is NerdyBot with your raid planning tool. Just follow the path by responding "
            "via the reaction presets or with chat input. Now, what would you like to do?"
            "\n\n"
            "<:check:809765339230896128>: schedule event\n"
            "--------------------------------------------\n"
            "<:add:809765525629698088>: create a new template\n"
            "<:edit:809884574497898557>: edit an existing template\n"
            "<:remove:809885458220974100>: remove an existing template\n"
            "--------------------------------------------\n"
            "<:cancel:809790666930126888>: cancel conversation",
        )

        reactions = {
            "<:check:809765339230896128>": RaidPlanerState.EVENT_CREATE,
            "<:edit2:810114710938189874>": RaidPlanerState.EVENT_EDIT,
            "<:add:809765525629698088>": RaidPlanerState.TEMPLATE_ADD,
            "<:edit:809884574497898557>": RaidPlanerState.TEMPLATE_EDIT,
            "<:remove:809885458220974100>": RaidPlanerState.TEMPLATE_REMOVE,
            "<:cancel:809790666930126888>": RaidPlanerState.CLOSE,
        }

        await self.send_react(emb, reactions)

    # region template
    async def conv_template_menu(self):
        emb = Embed(
            title="RaidPlaner",
            description="**Template Creator**"
            "\n\n"
            f"Template '{self.tmpTemplate.Name}' in the works. It is currently designed for "
            f"{self.tmpTemplate.PlayerCount}🧑‍🤝‍🧑 players and has "
            f"{self.tmpTemplate.get_encounter_count()} encounters."
            "\n\n"
            "<:edit2:810114710938189874>: change name and description\n"
            "--------------------------------------------\n"
            "<:add:809765525629698088>: add encounter\n"
            "<:edit:809884574497898557>: edit encounter\n"
            "<:remove:809885458220974100>: remove encounter\n"
            "--------------------------------------------\n"
            "<:preview:810222989450543116>: preview template\n"
            "--------------------------------------------\n"
            "<:check:809765339230896128>: save template\n"
            "<:cancel:809790666930126888>: cancel",
        )

        reactions = {
            "<:edit2:810114710938189874>": RaidPlanerState.TEMPLATE_NAME,
            "<:add:809765525629698088>": RaidPlanerState.TEMPLATE_ENCOUNTER_ADD,
            "<:edit:809884574497898557>": RaidPlanerState.TEMPLATE_ENCOUNTER_EDIT,
            "<:remove:809885458220974100>": RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE,
            "<:preview:810222989450543116>": RaidPlanerState.TEMPLATE_PREVIEW,
            "<:check:809765339230896128>": RaidPlanerState.TEMPLATE_SAVE,
            "<:cancel:809790666930126888>": RaidPlanerState.MAIN_MENU,
        }

        await self.send_react(emb, reactions)

    async def conv_template_set_name(self):
        emb = Embed(title="RaidPlaner", description="Give your template a new name. Just type it in the chat.")

        reactions = {
            "⏩": RaidPlanerState.TEMPLATE_DESC,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_DESC, self.set_template_name, reactions)

    async def conv_template_set_desc(self):
        emb = Embed(title="RaidPlaner", description="Write a few lines to describe your event.")

        reactions = {
            "⏩": RaidPlanerState.TEMPLATE_COUNT,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_COUNT, self.set_template_desc, reactions)

    async def conv_template_set_count(self):
        emb = Embed(title="RaidPlaner", description="For how many players is this event designed?")

        reactions = {
            "⏩": RaidPlanerState.TEMPLATE_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_MENU, self.set_template_count, reactions)

    async def conv_template_create(self):
        self.tmpTemplate = RaidTemplate(
            GuildId=self.guild.id,
            TemplateId=len(self.templates) + 1,
            Name=f"RaidTemplate {len(self.templates) + 1}",
            PlayerCount=10,
            CreateDate=datetime.utcnow(),
        )
        await self.conv_template_menu()

    async def conv_template_select(self):
        template_count = len(self.templates)
        if template_count == 0:
            return await self.conv_main_menu()

        emb = Embed(title="RaidPlaner", description="Type in the number referencing a template below:" "\n\n")

        for i in range(template_count):
            emb.description += f"**{i + 1}:** {self.templates[i].Name}\n"

        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.MAIN_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_MENU, self.set_edit_template, reactions)

    async def conv_template_remove(self):
        template_count = len(self.templates)
        if template_count == 0:
            return await self.conv_template_menu()

        emb = Embed(title="RaidPlaner", description="Type in the number referencing a template below:" "\n\n")

        for i in range(template_count):
            emb.description += f"**{i}:** {self.templates[i].Name}\n"

        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.MAIN_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_REMOVE_CONFIRM, self.set_edit_template, reactions)

    async def conv_template_remove_confirm(self):
        emb = Embed(
            title="RaidPlaner", description=f"Do your really want to remove template '{self.tmpTemplate.Name}'?"
        )

        reactions = {
            "<:check:809765339230896128>": RaidPlanerState.TEMPLATE_REMOVE_SAVE,
            "<:cancel:809790666930126888>": RaidPlanerState.MAIN_MENU,
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
        if len(answer) > 35:
            emb = Embed(title="RaidPlaner", description="Name can not be longer than 35 characters!")
            await self.send_ns(emb)
            return False
        if len(answer) < 5:
            emb = Embed(title="RaidPlaner", description="Name can not be less than 5 characters!")
            await self.send_ns(emb)
            return False
        self.tmpTemplate.Name = answer

    async def set_template_desc(self, answer):
        if len(answer) > 350:
            emb = Embed(title="RaidPlaner", description="The description can not be longer than 350 characters!")
            await self.send_ns(emb)
            return False
        self.tmpTemplate.Description = answer

    async def set_template_count(self, answer):
        if not answer.isdigit():
            emb = Embed(title="RaidPlaner", description="Please enter a valid numeric value!")
            await self.send_ns(emb)
            return False

        cnt = int(answer)

        if cnt < 3:
            emb = Embed(title="RaidPlaner", description="Value must be larger than 2!")
            await self.send_ns(emb)
            return False

        if cnt > 25:
            emb = Embed(title="RaidPlaner", description="The player count is limited to 25!")
            await self.send_ns(emb)
            return False
        self.tmpTemplate.PlayerCount = cnt

    async def set_edit_template(self, answer):
        if not answer.isdigit():
            emb = Embed(title="RaidPlaner", description="Please enter a valid numeric value!")
            await self.send_ns(emb)
            return False

        idx = int(answer)

        if idx > len(self.templates) or idx == 0:
            emb = Embed(title="RaidPlaner", description="Value is not inside the selectable range!")
            await self.send_ns(emb)
            return False

        self.tmpTemplate = self.templates[idx - 1]

    # endregion

    # region encounter
    async def conv_encounter_menu(self):
        emb = Embed(
            title="RaidPlaner",
            description="**Encounter Creator**"
            "\n\n"
            "Preview:"
            "\n\n"
            f"{self.tmpEncounter.info()}"
            "\n\n"
            "<:edit2:810114710938189874>: change name an description\n"
            "--------------------------------------------\n"
            "<:add:809765525629698088>: add new role\n"
            "<:edit:809884574497898557>: edit an existing role\n"
            "<:remove:809885458220974100>: remove an existing role\n"
            "--------------------------------------------\n"
            "<:check:809765339230896128>: finish encounter\n"
            "<:cancel:809790666930126888>: cancel encounter creation\n",
        )

        reactions = {
            "<:edit2:810114710938189874>": RaidPlanerState.TEMPLATE_ENCOUNTER_NAME,
            "<:add:809765525629698088>": RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD,
            "<:edit:809884574497898557>": RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT,
            "<:remove:809885458220974100>": RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE,
            "<:check:809765339230896128>": RaidPlanerState.TEMPLATE_ENCOUNTER_SAVE,
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_MENU,
        }

        await self.send_react(emb, reactions)

    async def conv_encounter_add(self):
        self.tmpEncounter = RaidEncounter(
            GuildId=self.guild.id,
            TemplateId=self.tmpTemplate.TemplateId,
            EncounterId=self.tmpTemplate.get_encounter_count() + 1,
            Name=f"Encounter {self.tmpTemplate.get_encounter_count() + 1}",
        )
        self.tmpEncounter.isNew = True
        await self.conv_encounter_menu()

    async def conv_encounter_select(self):
        encounter_count = self.tmpTemplate.get_encounter_count()
        if encounter_count == 0:
            return await self.conv_encounter_menu()

        emb = Embed(title="RaidPlaner", description="Type in the number referencing an encounter below:" "\n\n")

        for i in range(encounter_count):
            emb.description += f"**{i + 1}:** {self.tmpTemplate.Encounters[i].Name}\n"

        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_MENU, self.set_edit_encounter, reactions)

    async def conv_encounter_remove(self):
        encounter_count = self.tmpTemplate.get_encounter_count()
        if encounter_count == 0:
            return await self.conv_template_menu()

        emb = Embed(title="RaidPlaner", description="Type in the number referencing an encounter below:" "\n\n")

        for i in range(encounter_count):
            emb.description += f"**{i + 1}:** {self.tmpTemplate.Encounters[i].Name}\n"

        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE_CONFIRM, self.set_edit_encounter, reactions)

    async def conv_encounter_remove_confirm(self):
        emb = Embed(
            title="RaidPlaner", description=f"Do your really want to remove encounter {self.tmpEncounter.Name}?"
        )

        reactions = {
            "<:check:809765339230896128>": RaidPlanerState.TEMPLATE_ENCOUNTER_REMOVE_SAVE,
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_react(emb, reactions)

    async def conv_encounter_remove_save(self):
        self.tmpTemplate.Encounters.remove(self.tmpEncounter)
        await self.conv_template_menu()

    async def conv_encounter_name(self):
        emb = Embed(title="RaidPlaner", description=f"Give your encounter '{self.tmpEncounter.Name}' a new name.")

        reactions = {
            "⏩": RaidPlanerState.TEMPLATE_ENCOUNTER_DESC,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_DESC, self.set_encounter_name, reactions)

    async def conv_encounter_desc(self):
        emb = Embed(title="RaidPlaner", description="Write a few lines to describe your encounter.")

        reactions = {
            "⏩": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_MENU, self.set_encounter_desc, reactions)

    async def conv_encounter_save(self):
        cur_cnt = self.tmpEncounter.get_role_player_sum()
        if cur_cnt != self.tmpTemplate.PlayerCount:
            emb = Embed(
                title="RaidPlaner",
                description=f"The encounter does not match the required player count of "
                f"{self.tmpTemplate.PlayerCount}! It currently has {cur_cnt}.",
            )
            await self.send_ns(emb)
            await self.conv_encounter_menu()
        else:
            if self.tmpEncounter.isNew is True:
                self.tmpTemplate.Encounters.append(self.tmpEncounter)
                self.tmpEncounter.isNew = False
            await self.conv_template_menu()

    async def set_encounter_name(self, answer):
        if len(answer) > 35:
            emb = Embed(title="RaidPlaner", description="Name can not be longer than 35 characters!")
            await self.send_ns(emb)
            return False
        if len(answer) < 5:
            emb = Embed(title="RaidPlaner", description="Name can not be less than 5 characters!")
            await self.send_ns(emb)
            return False
        self.tmpEncounter.Name = answer

    async def set_encounter_desc(self, answer):
        if len(answer) > 150:
            emb = Embed(title="RaidPlaner", description="Description can not be longer than 150 characters!")
            await self.send_ns(emb)
            return False
        self.tmpEncounter.Description = answer

    async def set_edit_encounter(self, answer):
        if not answer.isdigit():
            emb = Embed(title="RaidPlaner", description="Please enter a valid numeric value!")
            await self.send_ns(emb)
            return False

        idx = int(answer)

        if idx > self.tmpTemplate.get_encounter_count() or idx == 0:
            emb = Embed(title="RaidPlaner", description="Value is not inside the selectable range!")
            await self.send_ns(emb)
            return False

        self.tmpEncounter = self.tmpTemplate.Encounters[idx]
        self.tmpEncounter.Roles.sort(key=lambda r: r.SortIndex)

    # endregion

    # region role
    async def conv_role_add(self):
        emb = Embed(
            title="RaidPlaner", description="Name the role you would like to add. First character must be an emoji!"
        )
        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_DESC, self.create_new_role, reactions)

    async def conv_role_add_desc(self):
        emb = Embed(title="RaidPlaner", description="Add a short description for the role.")

        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_COUNT, self.set_role_desc, reactions)

    async def conv_role_add_count(self):
        emb = Embed(title="RaidPlaner", description="How many players can apply for this role.")
        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_SORT, self.set_role_count, reactions)

    async def conv_role_add_sort(self):
        emb = Embed(
            title="RaidPlaner", description="Set the index by which the role should be sorted inside the encounter."
        )
        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_SAVE, self.set_role_sort, reactions)

    async def conv_role_edit_select(self):
        role_count = self.tmpEncounter.get_role_count()
        if role_count == 0:
            return await self.conv_encounter_menu()

        emb = Embed(title="RaidPlaner", description="Type in the number referencing a role below:" "\n\n")

        for i in range(role_count):
            emb.description += f"**{i + 1}:** {self.tmpEncounter.Roles[i]}\n"

        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_NAME, self.set_edit_role, reactions)

    async def conv_role_edit_name(self):
        emb = Embed(
            title="RaidPlaner",
            description=f"Give your role '{self.tmpRole.Name}' a new name. Remember: First character must be "
            f"an emoji!",
        )
        reactions = {
            "⏩": RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_DESC,
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_DESC, self.set_role_name, reactions)

    async def conv_role_edit_desc(self):
        emb = Embed(
            title="RaidPlaner",
            description="Give your role a new description. Your current description:"
            "\n\n"
            f"*{self.tmpRole.Description}*",
        )

        reactions = {
            "⏩": RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_COUNT,
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_ADD_COUNT, self.set_role_desc, reactions)

    async def conv_role_edit_count(self):
        emb = Embed(
            title="RaidPlaner",
            description=f"How many players can apply for this role. Currently it's {self.tmpRole.Count}.",
        )
        reactions = {
            "⏩": RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_SORT,
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }

        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_EDIT_SORT, self.set_role_count, reactions)

    async def conv_role_edit_sort(self):
        emb = Embed(
            title="RaidPlaner", description=f"Set the sort index for the role. Currently it's {self.tmpRole.SortIndex}."
        )
        reactions = {
            "<:check:809765339230896128>": RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_SAVE,
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
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

        emb = Embed(title="RaidPlaner", description="Type in the number referencing a role below:" "\n\n")

        for i in range(role_count):
            emb.description += f"**{i}:** {self.tmpEncounter.Roles[i]}\n"

        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_both(emb, RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE_CONFIRM, self.set_edit_role, reactions)

    async def conv_remove_role_confirm(self):
        emb = Embed(title="RaidPlaner", description=f"Do your really want to remove role '{self.tmpRole.Name}'?")

        reactions = {
            "<:check:809765339230896128>": RaidPlanerState.TEMPLATE_ENCOUNTER_ROLE_REMOVE_SAVE,
            "<:cancel:809790666930126888>": RaidPlanerState.TEMPLATE_ENCOUNTER_MENU,
        }
        await self.send_react(emb, reactions)

    async def conv_remove_role_save(self):
        self.tmpEncounter.Roles.remove(self.tmpRole)
        self.tmpEncounter.Roles.sort(key=lambda r: r.SortIndex)
        await self.conv_encounter_menu()

    async def create_new_role(self, answer):
        self.tmpRole = RaidEncounterRole(
            GuildId=self.guild.id,
            TemplateId=self.tmpEncounter.TemplateId,
            EncounterId=self.tmpEncounter.EncounterId,
        )
        self.tmpRole.isNew = True
        if await self.set_role_name(answer) is not None:
            return False

    async def set_role_name(self, answer):
        # todo extract and validate emoji
        self.tmpRole.Name = answer

    async def set_role_desc(self, answer):
        if len(answer) > 150:
            emb = Embed(title="RaidPlaner", description="Description can not be longer than 150 characters!")
            await self.send_ns(emb)
            return False
        self.tmpRole.Description = answer

    async def set_role_count(self, answer):
        if not answer.isdigit():
            emb = Embed(title="RaidPlaner", description="Please enter a valid numeric value!")
            await self.send_ns(emb)
            return False

        cnt = int(answer)

        if cnt > self.tmpTemplate.PlayerCount:
            emb = Embed(title="RaidPlaner", description="Value exceeds the maximum player count of this event!")
            await self.send_ns(emb)
            return False

        chk = self.tmpEncounter.get_role_player_sum()
        if self.tmpRole.isNew is not True:
            chk -= self.tmpRole.Count
        if chk + cnt > self.tmpTemplate.PlayerCount:
            emb = Embed(
                title="RaidPlaner",
                description="Combined with all other roles this would exceed the player count of this event!",
            )
            await self.send_ns(emb)
            return False

        if cnt <= 0:
            emb = Embed(title="RaidPlaner", description="Value must be larger than 0!")
            await self.send_ns(emb)
            return False

        self.tmpRole.Count = cnt

    async def set_role_sort(self, answer):
        if not answer.isdigit():
            emb = Embed(title="RaidPlaner", description="Please enter a valid numeric value!")
            await self.send_ns(emb)
            return False

        cnt = int(answer)

        if cnt <= 0:
            emb = Embed(title="RaidPlaner", description="Value must be larger than 0!")
            await self.send_ns(emb)
            return False

        self.tmpRole.SortIndex = cnt

    async def set_edit_role(self, answer):
        if not answer.isdigit():
            emb = Embed(title="RaidPlaner", description="Please enter a valid numeric value!")
            await self.send_ns(emb)
            return False

        idx = int(answer)

        if idx > self.tmpEncounter.get_role_count() or idx == 0:
            emb = Embed(title="RaidPlaner", description="Value is not inside the selectable range!")
            await self.send_ns(emb)
            return False

        self.tmpRole = self.tmpEncounter.Roles[idx - 1]

    # endregion

    # region event creation
    async def conv_create_event(self):
        self.tmpEvent = RaidEvent()
        await self.conv_create_event_template()

    async def conv_create_event_template(self):
        template_count = len(self.templates)
        if template_count == 0:
            return await self.conv_main_menu()

        emb = Embed(title="RaidPlaner")

        for i in range(template_count):
            val = ""
            if self.templates[i].Description is not None:
                val = self.templates[i].Description + "\n"

            val += f"Players: {self.templates[i].PlayerCount}\n"
            val += f"Encounters: {self.templates[i].get_encounter_count()}"

            emb.add_field(name=f"`{i + 1}`: {self.templates[i].Name}", value=val)

        reactions = {
            "<:cancel:809790666930126888>": RaidPlanerState.MAIN_MENU,
        }
        await self.send_both(emb, RaidPlanerState.EVENT_CREATE_NAME, self.set_edit_template, reactions)

    async def conv_create_event_name(self):
        emb = Embed(title="RaidPlaner", description="Give your RaidEvent a name. Just type it in the chat.")

        await self.send_msg(emb, RaidPlanerState.EVENT_CREATE_DESC, self.set_event_name)

    async def conv_create_event_desc(self):
        emb = Embed(
            title="RaidPlaner",
            description="Write a few lines to describe your event. This will overwrite the description of the "
            "template.",
        )

        reactions = {
            "⏩": RaidPlanerState.EVENT_CREATE_START,
        }
        await self.send_both(emb, RaidPlanerState.EVENT_CREATE_START, self.set_event_desc, reactions)

    async def set_event_name(self, answer):
        if len(answer) > 35:
            emb = Embed(title="RaidPlaner", description="Name can not be longer than 35 characters!")
            await self.send_ns(emb)
            return False
        if len(answer) < 5:
            emb = Embed(title="RaidPlaner", description="Name can not be less than 5 characters!")
            await self.send_ns(emb)
            return False
        self.tmpEvent.Name = answer

    async def set_event_desc(self, answer):
        if len(answer) > 350:
            emb = Embed(title="RaidPlaner", description="The description can not be longer than 350 characters!")
            await self.send_ns(emb)
            return False
        self.tmpEvent.Description = answer

    # endregion

    async def create_template_preview(self):
        await self.send_ns(embed=self.tmpTemplate.create_embed())
        emb = Embed(title="RaidPlaner", description="Above you can see the preview. Looking good eh?")

        reactions = {
            "👍": RaidPlanerState.MAIN_MENU,
        }
        await self.send_react(emb, reactions)

    def refresh_data(self):
        with self.bot.session_scope() as session:
            self.templates = RaidTemplate.get_from_guild(self.guild.id, session)


def setup(bot):
    """adds this module to the bot"""
    bot.add_cog(RaidPlaner(bot))
