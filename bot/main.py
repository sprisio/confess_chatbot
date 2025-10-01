import logging
import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils.exceptions import MessageNotModified, ChatNotFound

# --- Make sure you have these files in the same 'bot' directory ---
# Note: These files (config.py, db.py, utils.py) are assumed to exist and are not part of this script.
from config import BOT_TOKEN, CHANNEL_USERNAME, NOTIFY_DELTA
from db import init_db, fetchrow, fetch, execute, close_db
from utils import sanitize_text, encrypt_userid, decrypt_userid

logging.basicConfig(level=logging.INFO)

# --- Bot Initialization ---
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

CATEGORIES = ['💔 Love', '💼 Work', '👨‍👩‍👧 Family', '😔 Mental Health', '😜 Funny', '🎲 Random']
CONFESSION_COOLDOWN = datetime.timedelta(minutes=5)

# -------------------- FSMs (State Machines) --------------------
class ConfessState(StatesGroup):
    waiting_category = State()
    waiting_text = State()

class CommentState(StatesGroup):
    waiting_text = State()

# -------------------- Bot Commands --------------------
@dp.message_handler(commands=['start'], state='*')
async def cmd_start(m: types.Message, state: FSMContext):
    # If a state exists, cancel it first.
    current_state = await state.get_state()
    if current_state is not None:
        await state.finish()

    args = m.get_args()
    if args and args.startswith('comment_'):
        try:
            confession_id = int(args.split('_')[1])
            # FIX 3: Fetch confession text to provide context
            confession = await fetchrow("SELECT id, text FROM confessions WHERE id=$1", confession_id)
            if confession:
                await state.update_data(confession_id=confession_id)
                
                # FIX 3: Reply with the original confession text quoted
                reply_text = (
                    f"You are leaving an anonymous comment for confession #{confession_id}:\n\n"
                    f"<blockquote>{sanitize_text(confession['text'])}</blockquote>\n\n"
                    "<b>Please type your comment below:</b>"
                )
                await m.reply(reply_text, parse_mode=types.ParseMode.HTML)
                await CommentState.waiting_text.set()
            else:
                await m.reply("Sorry, the confession you're trying to comment on doesn't exist anymore.")
        except (ValueError, IndexError):
            await m.reply("Invalid comment link.")
        return

    # FIX 1: Improved welcome message with clear calls to action.
    welcome_text = (
        "Welcome! I am the Anonymous Confession Bot. 🤫\n\n"
        "You can share your thoughts, secrets, and stories anonymously.\n\n"
        "➡️ Use /confess to post a new confession.\n"
        "➡️ Use /help to see everything I can do."
    )
    await m.reply(welcome_text)


@dp.message_handler(commands=['help'], state='*')
async def cmd_help(m: types.Message, state: FSMContext):
    # If a state exists, cancel it first.
    current_state = await state.get_state()
    if current_state is not None:
        await state.finish()
        
    # FIX: Wrapped commands in backticks to prevent Markdown parsing errors.
    help_text = (
        "👋 *Hello! I'm the Anonymous Confession Bot.*\n\n"
        "I'm here to provide a safe space for you to share your thoughts, secrets, and stories anonymously.\n\n"
        "*Here are the commands you can use:*\n\n"
        "`🔹 /confess` - Start the process of posting a new anonymous confession.\n\n"
        "`🔹 /leaderboard` - See the most popular confessions! You'll get options to view the top posts from today or this week.\n\n"
        "`🔹 /my_confessions` - View a list of all the confessions you have personally made.\n\n"
        "`🔹 /help` - Show this message again.\n\n"
        "Your identity is always kept secret. Feel free to express yourself."
    )
    await m.reply(help_text, parse_mode=types.ParseMode.MARKDOWN)


@dp.message_handler(commands=['confess'])
async def cmd_confess(m: types.Message):
    user_id = m.from_user.id
    last_confession = await fetchrow("SELECT created_at FROM confessions WHERE author_id = $1 ORDER BY created_at DESC LIMIT 1", user_id)

    if last_confession:
        time_since = datetime.datetime.now(datetime.timezone.utc) - last_confession['created_at']
        if time_since < CONFESSION_COOLDOWN:
            remaining = CONFESSION_COOLDOWN - time_since
            minutes, seconds = divmod(int(remaining.total_seconds()), 60)
            await m.reply(f"Please wait {minutes}m {seconds}s before confessing again.")
            return

    # Create an inline keyboard for categories and the cancel button
    inline_kb = types.InlineKeyboardMarkup(row_width=2)
    # Create buttons for categories
    category_buttons = [types.InlineKeyboardButton(cat, callback_data=f"category:{cat}") for cat in CATEGORIES]
    inline_kb.add(*category_buttons)
    # Add the cancel button on its own row at the bottom
    inline_kb.row(types.InlineKeyboardButton("❌ Cancel Confession", callback_data="cancel_confession"))

    await m.reply("Pick a category for your confession:", reply_markup=inline_kb)
    await ConfessState.waiting_category.set()

# -------------------- Confession Flow --------------------
@dp.callback_query_handler(lambda c: c.data.startswith('category:'), state=ConfessState.waiting_category)
async def category_chosen(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer() # Acknowledge the button press
    category = cb.data.split(':', 1)[1] # Extract category from callback_data
    await state.update_data(category=category)
    
    # Edit the message to remove the category buttons and ask for text
    await cb.message.edit_text("Type your confession below. It will be posted anonymously.")
    
    # Add inline cancel button for text input stage, sent as a new message
    inline_cancel_kb = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("❌ Cancel Confession", callback_data="cancel_confession")
    )
    await bot.send_message(cb.from_user.id, "Remember, you can always stop.", reply_markup=inline_cancel_kb)
    await ConfessState.waiting_text.set()

@dp.message_handler(state=ConfessState.waiting_text)
async def receive_confession(m: types.Message, state: FSMContext):
    data = await state.get_data()
    category = data.get('category')
    text = sanitize_text(m.text)
    author_id = m.from_user.id

    if not text or len(text) < 5:
        await m.reply("Your confession seems too short. Please try again with at least 5 characters.")
        # User is still in ConfessState.waiting_text, so the cancel button remains
        return

    inline = types.InlineKeyboardMarkup(row_width=2)
    inline.add(
        types.InlineKeyboardButton("👍 Relatable (0)", callback_data="react:relatable:0"),
        types.InlineKeyboardButton("❤️ Support (0)", callback_data="react:support:0"),
        types.InlineKeyboardButton("💬 Comments (0)", callback_data="viewcomments:0"),
        types.InlineKeyboardButton("➕ Add Comment", callback_data="givecomment:0")
    )

    posted = await bot.send_message(CHANNEL_USERNAME, f"{category} Anonymous Confession\n\n\"{text}\"", reply_markup=inline)
    enc_author = encrypt_userid(author_id)

    row = await fetchrow("""
        INSERT INTO confessions(author_id, author_user_id, channel_chat_id, channel_message_id, category, text)
        VALUES($1, $2, $3, $4, $5, $6) RETURNING id
    """, author_id, enc_author, posted.chat.id, posted.message_id, category, text)
    confession_id = row['id']

    new_inline = types.InlineKeyboardMarkup(row_width=2)
    new_inline.add(
        types.InlineKeyboardButton("👍 Relatable (0)", callback_data=f"react:relatable:{confession_id}"),
        types.InlineKeyboardButton("❤️ Support (0)", callback_data=f"react:support:{confession_id}"),
        types.InlineKeyboardButton(f"💬 Comments (0)", callback_data=f"viewcomments:{confession_id}"),
        types.InlineKeyboardButton("➕ Add Comment", callback_data=f"givecomment:{confession_id}")
    )
    await bot.edit_message_reply_markup(chat_id=posted.chat.id, message_id=posted.message_id, reply_markup=new_inline)

    link = f"https://t.me/{CHANNEL_USERNAME.strip('@')}/{posted.message_id}"
    await m.reply(f"✅ Your confession has been posted anonymously!\n\n🔗 View it here: {link}\n\nSee /leaderboard to see top confessions!")
    await state.finish()

# -------------------- Cancel Confession Handler --------------------
@dp.callback_query_handler(lambda c: c.data == 'cancel_confession', state=ConfessState.all_states)
async def cancel_confession(cb: types.CallbackQuery, state: FSMContext):
    await cb.answer("Confession cancelled.", show_alert=False)
    await state.finish()
    try:
        await cb.message.edit_text("❌ Your confession has been cancelled.")
    except Exception as e:
        # Fallback if editing fails (e.g., message is too old)
        logging.warning(f"Could not edit message on cancel: {e}")
        await bot.send_message(cb.from_user.id, "❌ Your confession has been cancelled.")


# -------------------- Notifications and Reactions --------------------
async def update_reactions_and_notify(conf_id: int, user_id: int, notification_type: str):
    counts = await fetch("SELECT reaction_type, COUNT(*) AS c FROM reactions WHERE confession_id=$1 GROUP BY reaction_type", conf_id)
    mapping = {r['reaction_type']: r['c'] for r in counts}
    r_rel = mapping.get('relatable', 0)
    r_sup = mapping.get('support', 0)

    comments_count_row = await fetchrow("SELECT COUNT(*) as c FROM comments WHERE confession_id=$1", conf_id)
    c_count = comments_count_row['c'] if comments_count_row else 0

    row = await fetchrow("SELECT channel_chat_id, channel_message_id, author_id FROM confessions WHERE id=$1", conf_id)
    if not row:
        return

    chat_id, msg_id, author_id = row['channel_chat_id'], row['channel_message_id'], row['author_id']
    
    new_inline = types.InlineKeyboardMarkup(row_width=2)
    new_inline.add(
        types.InlineKeyboardButton(f"👍 Relatable ({r_rel})", callback_data=f"react:relatable:{conf_id}"),
        types.InlineKeyboardButton(f"❤️ Support ({r_sup})", callback_data=f"react:support:{conf_id}"),
        types.InlineKeyboardButton(f"💬 Comments ({c_count})", callback_data=f"viewcomments:{conf_id}"),
        types.InlineKeyboardButton("➕ Add Comment", callback_data=f"givecomment:{conf_id}")
    )
    
    try:
        await bot.edit_message_reply_markup(chat_id=chat_id, message_id=msg_id, reply_markup=new_inline)
    except MessageNotModified:
        pass # Ignore if markup is the same
    except Exception as e:
        logging.warning(f"Could not edit message markup for {conf_id}: {e}")

    # Notify author if it's not their own action
    if author_id != user_id:
        link = f"https://t.me/{CHANNEL_USERNAME.strip('@')}/{msg_id}"
        if notification_type == 'reaction':
            message = f"🎉 Someone reacted to your confession #{conf_id}!\n\nTap to view: {link}"
        else: # 'comment'
            message = f"💬 Someone commented on your confession #{conf_id}!\n\nTap to view: {link}"
        
        try:
            await bot.send_message(author_id, message)
        except ChatNotFound:
            logging.warning(f"Could not send notification to author {author_id}: Chat not found (user might have blocked the bot).")
        except Exception as e:
            logging.error(f"Could not send notification to author {author_id}: {e}")


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('react:'), state='*')
async def on_react(cb: types.CallbackQuery):
    _, rtype, conf_id_str = cb.data.split(':')
    conf_id = int(conf_id_str)
    user_id = cb.from_user.id

    if conf_id == 0:
        await cb.answer("Please wait a moment...", show_alert=True)
        return

    try:
        await execute("INSERT INTO reactions(confession_id, user_id, reaction_type) VALUES($1,$2,$3)", conf_id, user_id, rtype)
        await cb.answer("Thanks for reacting!")
        await update_reactions_and_notify(conf_id, user_id, notification_type='reaction')
    except Exception:
        await cb.answer("You've already reacted with this type.")
        return

# -------------------- Commenting Flow --------------------
@dp.callback_query_handler(lambda c: c.data and c.data.startswith('givecomment:'), state='*')
async def on_add_comment(cb: types.CallbackQuery):
    # Answer the callback query immediately to prevent timeout errors
    await cb.answer()

    confession_id = int(cb.data.split(':')[1])
    
    if confession_id == 0:
        logging.warning("User clicked on givecomment button with confession_id 0")
        return

    bot_info = await bot.get_me()
    comment_link = f"https://t.me/{bot_info.username}?start=comment_{confession_id}"
    
    try:
        await bot.send_message(
            cb.from_user.id,
            f"To leave an anonymous comment on confession #{confession_id}, please click the button below.",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("➡️ Leave a Comment", url=comment_link)
            )
        )
    except ChatNotFound:
        await bot.send_message(cb.from_user.id, "I couldn't send you the comment link because I can't start a chat with you. Please start a chat with me first!")
    except Exception:
        await bot.send_message(cb.from_user.id, "I couldn't send you the comment link. Have you started a chat with me and are you not blocking me?")


@dp.message_handler(state=CommentState.waiting_text)
async def handle_comment(m: types.Message, state: FSMContext):
    data = await state.get_data()
    confession_id = data.get('confession_id')
    text = m.text.strip()
    commenter_id = m.from_user.id

    if not confession_id:
        await m.reply("Something went wrong. Please try commenting again.")
        await state.finish()
        return
    if not text:
        await m.reply("A comment cannot be empty. Please try again.")
        return

    try:
        confession = await fetchrow("SELECT channel_chat_id, channel_message_id, author_id FROM confessions WHERE id=$1", confession_id)
        if not confession:
            await m.reply("This confession does not seem to exist anymore.")
            await state.finish()
            return

        await execute("INSERT INTO comments(confession_id, commenter_user_id, text) VALUES($1,$2,$3)", confession_id, commenter_id, text)

        comment_message = f"💬 Anonymous Comment:\n\n\"{text}\""
        await bot.send_message(
            chat_id=confession['channel_chat_id'], text=comment_message, reply_to_message_id=confession['channel_message_id']
        )
        
        await m.reply("✅ Your anonymous comment has been posted!")
        
        await update_reactions_and_notify(confession_id, commenter_id, notification_type='comment')

    except Exception as e:
        logging.error(f"Failed to save comment for confession {confession_id}: {e}")
        await m.reply("❌ An error occurred while saving your comment.")
    finally:
        await state.finish()


@dp.callback_query_handler(lambda c: c.data and c.data.startswith('viewcomments:'), state='*')
async def view_comments(cb: types.CallbackQuery):
    confession_id = int(cb.data.split(':')[1])
    if confession_id == 0:
        await cb.answer("Please wait a moment...", show_alert=True)
        return
    rows = await fetch("SELECT text FROM comments WHERE confession_id=$1", confession_id)
    if not rows:
        await cb.answer("No comments yet.", show_alert=True)
        return
    comment_text = "\n\n".join([f"💬 \"{r['text']}\"" for r in rows])
    try:
        await bot.send_message(cb.from_user.id, f"📜 Comments for confession #{confession_id}:\n\n{comment_text}")
        await cb.answer()
    except ChatNotFound:
        await cb.answer("I couldn't send you the comments because I can't start a chat with you. Please start a chat with me first!", show_alert=True)
    except Exception:
        await cb.answer("I couldn't send you the comments. Have you started a chat with me?", show_alert=True)

# -------------------- Leaderboard and My Confessions --------------------
@dp.message_handler(commands=['leaderboard'])
async def leaderboard_menu(m: types.Message):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🏆 Weekly", callback_data="leaderboard:week"),
        types.InlineKeyboardButton("📅 Daily", callback_data="leaderboard:day")
    )
    await m.reply("Select a leaderboard to view:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('leaderboard:'))
async def show_leaderboard(cb: types.CallbackQuery):
    period = cb.data.split(':')[1]
    
    interval = '1 DAY' if period == 'day' else '7 DAY'
    title = 'Daily' if period == 'day' else 'Weekly'

    query = f"""
        SELECT c.id, c.text, COUNT(r.id) as total_reactions
        FROM confessions c
        LEFT JOIN reactions r ON c.id = r.confession_id
        WHERE c.created_at >= NOW() - INTERVAL '{interval}'
        GROUP BY c.id, c.text
        ORDER BY total_reactions DESC, c.id DESC
        LIMIT 10
    """
    rows = await fetch(query)

    if not rows:
        await cb.message.edit_text(f"No confessions with reactions found for the {title} leaderboard.")
        await cb.answer()
        return

    lines = [f"🏆 Top 10 Confessions ({title})\n"]
    for i, r in enumerate(rows, start=1):
        snippet = (r['text'][:70] + '...') if len(r['text']) > 70 else r['text']
        lines.append(f"{i}. #{r['id']}: \"{snippet}\" — Reactions: {r['total_reactions']}")
    
    await cb.message.edit_text("\n".join(lines))
    await cb.answer()

@dp.message_handler(commands=['my_confessions'])
async def my_confessions_menu(m: types.Message):
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("Today's Confessions", callback_data="my_confessions:day"),
        types.InlineKeyboardButton("This Week's Confessions", callback_data="my_confessions:week"),
        types.InlineKeyboardButton("All My Confessions", callback_data="my_confessions:all")
    )
    await m.reply("Select a time period to view your confessions:", reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('my_confessions:'))
async def show_my_confessions(cb: types.CallbackQuery):
    period = cb.data.split(':')[1]
    user_id = cb.from_user.id

    where_clause = "WHERE c.author_id = $1"
    params = [user_id]
    if period == 'day':
        where_clause += " AND c.created_at >= NOW() - INTERVAL '1 DAY'"
        title = "Today's"
    elif period == 'week':
        where_clause += " AND c.created_at >= NOW() - INTERVAL '7 DAY'"
        title = "This Week's"
    else:
        title = "All Your"

    query = f"""
        SELECT c.id, c.text, c.channel_message_id, COUNT(r.id) as total_reactions
        FROM confessions c
        LEFT JOIN reactions r ON c.id = r.confession_id
        {where_clause}
        GROUP BY c.id, c.text, c.channel_message_id
        ORDER BY c.id DESC
    """
    rows = await fetch(query, *params)

    if not rows:
        await cb.message.edit_text(f"You have not made any confessions in this time period.")
        await cb.answer()
        return

    lines = [f"📜 {title} Confessions:\n"]
    for r in rows:
        link = f"https://t.me/{CHANNEL_USERNAME.strip('@')}/{r['channel_message_id']}"
        snippet = (r['text'][:50] + '...') if len(r['text']) > 50 else r['text']
        lines.append(f"• \"{snippet}\" - [View]({link}) ({r['total_reactions']} reactions)")

    await cb.message.edit_text("\n".join(lines), parse_mode=types.ParseMode.MARKDOWN, disable_web_page_preview=True)
    await cb.answer()


# -------------------- Startup / Shutdown Hooks --------------------
async def on_startup(dispatcher):
    await init_db()

async def on_shutdown(dispatcher):
    await close_db()

# -------------------- Main Entry Point --------------------
if __name__ == "__main__":
    executor.start_polling(
        dp,
        on_startup=on_startup,
        on_shutdown=on_shutdown,
        skip_updates=True
    )

