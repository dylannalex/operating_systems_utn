"""
This file contains classes with tasks that, given
the user inputs, computes and shows the results
"""

import os
import telegram
import telegram.ext
from datetime import datetime
from os_utn.database import database
from os_utn.database import settings as db_settings
from os_utn.tgm import context_buffer as cb
from os_utn.operating_system.processes import process
from os_utn.operating_system.processes import scheduler
from os_utn.operating_system.processes import chart
from os_utn.operating_system.tools import units_converter
from os_utn.operating_system.memory import paging
from os_utn.tgm.task import text
from os_utn import settings as repo_settings

from mysql.connector.connection_cext import CMySQLConnection


def send_result_messages(
    update: telegram.Update,
    context: telegram.ext.CallbackContext,
    db: CMySQLConnection,
    task_id: int,
    result_message: str,
):
    # Send result message
    if result_message:
        context.bot.sendMessage(
            parse_mode="MarkdownV2",
            text=result_message,
            chat_id=update.effective_user["id"],
        )

    support_me_button = telegram.InlineKeyboardButton(
        text=text.SUPPORT_ME_BUTTON, url=repo_settings.GITHUB_REPO_LINK
    )

    # Send 'support me' message
    context.bot.sendMessage(
        parse_mode="MarkdownV2",
        text=text.SUPPORT_ME_MESSAGE,
        chat_id=update.effective_user["id"],
        reply_markup=telegram.InlineKeyboardMarkup([[support_me_button]]),
    )

    # Save task log
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    database.add_task_log(
        db,
        cb.DatabaseBuffer.get_task_start_time(context),
        now,
        update.effective_user["id"],
        task_id,
    )


class ProcessesScheduling:
    def _get_plot_path(user_id: str):
        return os.path.abspath(f"./os_utn/tgm/img/{user_id}.png")

    def _parse_processes(processes_string: str) -> list[process.InteractiveProcess]:
        """
        Parses the given processes string.

        @processes_string: process_name-arrival_time-total_executions|process_name-arrival_time-total_executions...

        Example:
            A-1-5,B-2-6,C-3-8
            >>> [process.Process("A", 1, 5), process.Process("B", 2, 6), process.Process("C", 3, 8)]
        """
        processes_list = [l.split("-") for l in processes_string.split(",")]
        return [
            process.InteractiveProcess(p[0], int(p[1]), int(p[2]))
            for p in processes_list
        ]

    def show_processes_execution(
        update: telegram.Update,
        context: telegram.ext.CallbackContext,
        db: CMySQLConnection,
    ):
        processes = ProcessesScheduling._parse_processes(
            cb.ProcessesSchedulingBuffer.get_processes(context)
        )
        scheduling_algo = cb.ProcessesSchedulingBuffer.get_scheduling_algorithm(context)
        chat_id = update.effective_user["id"]

        if scheduling_algo == cb.ProcessesSchedulingBuffer.RR_SA:
            table = scheduler.InteractiveSystem.round_robin(
                processes,
                cb.ProcessesSchedulingBuffer.get_time_slice(context),
                cb.ProcessesSchedulingBuffer.get_with_modification(context),
                [cb.ProcessesSchedulingBuffer.get_modification_change(context)],
            )
            task_id = db_settings.ROUND_ROBIN_TASK_ID

        elif scheduling_algo == cb.ProcessesSchedulingBuffer.SJF_SA:
            table = scheduler.BatchSystem.shortest_job_first(processes)
            task_id = db_settings.SJF_TASK_ID

        elif scheduling_algo == cb.ProcessesSchedulingBuffer.SRTN_SA:
            table = scheduler.BatchSystem.shortest_remaining_time_next(processes)
            task_id = db_settings.SRTN_TASK_ID

        elif scheduling_algo == cb.ProcessesSchedulingBuffer.FCFS_SA:
            table = scheduler.BatchSystem.first_come_first_served(processes)
            task_id = db_settings.FCFS_TASK_ID

        # Get path were the plot will be stored
        chat_id = update.effective_user["id"]
        plot_path = ProcessesScheduling._get_plot_path(chat_id)

        # Generate plot and send it
        chart.chart(table, plot_path)
        context.bot.sendPhoto(
            chat_id=chat_id,
            photo=open(plot_path, "rb"),
        )

        send_result_messages(
            update,
            context,
            db,
            task_id,
            text.PROCESSES_SCHEDULING_RESULT(
                scheduling_algo, table.get_execution_string()
            ),
        )

        # Remove plot
        os.remove(plot_path)


class Paging:
    def get_page_number(logical_address: str, page_size: int):
        return paging.get_page_number(logical_address, page_size)

    def convert_page_size(page_size: str):
        return units_converter.convert_size_unit_to_bytes(
            *units_converter.decompose_number(page_size)
        )

    def translate_logical_to_real(
        update: telegram.Update,
        context: telegram.ext.CallbackContext,
        db: CMySQLConnection,
    ):
        (
            logical_address,
            page_size,
            page_frame,
        ) = cb.PagingBuffer.get_logical_to_real_parameters(context)

        real_address = paging.get_real_address(logical_address, page_size, page_frame)

        send_result_messages(
            update,
            context,
            db,
            db_settings.TRANSLATE_LOGICAL_TO_REAL_TASK_ID,
            text.TRANSLATE_LOGICAL_TO_REAL_RESULT(real_address),
        )

    def real_address_length(
        update: telegram.Update,
        context: telegram.ext.CallbackContext,
        db: CMySQLConnection,
    ):
        frame_number = cb.PagingBuffer.get_frame_number(context)
        frame_size = cb.PagingBuffer.get_frame_size(context)

        real_address_length = paging.get_physical_address_length(
            int(frame_number), int(frame_size)
        )

        send_result_messages(
            update,
            context,
            db,
            db_settings.REAL_ADDRESS_LENGTH_TASK_ID,
            text.REAL_ADDRESS_LENGTH_RESULT(real_address_length),
        )

    def logical_address_length(
        update: telegram.Update,
        context: telegram.ext.CallbackContext,
        db: CMySQLConnection,
    ):
        page_number = cb.PagingBuffer.get_page_number(context)
        page_size = cb.PagingBuffer.get_page_size(context)

        logical_address_length_ = paging.get_physical_address_length(
            int(page_number), int(page_size)
        )

        send_result_messages(
            update,
            context,
            text.LOGICAL_ADDRESS_LENGTH_RESULT(logical_address_length_),
        )
