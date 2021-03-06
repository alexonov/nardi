"""
Main rules:
    1. bearing off only if all home
    2. overshooting bearing off only if no other non-bear-off move

    3. only once from the head unless first move
    4. not blocking 6 in a row (unless there's a checker in front)
    5. play both dice when possible
    6. if only one die can be played - play biggest

"""
import itertools

from game.components import Board
from game.components import Colors
from game.components import convert_coordinates
from game.components import MAX_POSITION
from game.components import MoveNotPossibleError
from game.components import SingleMove


MOVE_CACHE = {}
MOVE_BOARD_DICTIONARY = {}


def init_cache(board):
    global MOVE_CACHE
    global MOVE_BOARD_DICTIONARY

    MOVE_CACHE = {'board': board.export_position(), 'moves': {}}
    MOVE_BOARD_DICTIONARY = {}


def get_board_from_cache(move):
    # check that the move is valid
    current_node = MOVE_CACHE
    afterstate = current_node['board']

    counter = 0
    for i, m in enumerate(move):
        counter = i
        try:
            current_node = current_node['moves'][str(m)]
            afterstate = current_node['board']
        except KeyError:
            break

    fake_board = Board.generate_from_position(afterstate)

    # complete moves if left
    for ind in range(counter, len(move)):
        m = move[ind]
        fake_board.do_single_move(m)

        # save to cache
        current_node['moves'][str(m)] = {
            'board': fake_board.export_position(),
            'moves': {},
        }
        current_node = current_node['moves'][str(m)]

    MOVE_BOARD_DICTIONARY[str(move)] = fake_board.export_position()
    return fake_board


def passes_rule_six_block(move: list[SingleMove]) -> bool:
    """
    not blocking 6 in a row (unless there's a checker in front)

    also checks if move is valid
    """
    try:
        fake_board = get_board_from_cache(move)
    except MoveNotPossibleError:
        return False

    # check if there are 6-blocks after the move
    blocks = fake_board.find_blocks_min_length(move[-1].color, 6)
    if len(blocks) == 0:
        return True

    opponent_color = Colors.opponent(move[-1].color)

    # check each block if it can be legally allowed
    for b in blocks:
        # take last position
        last_position = b[-1]

        # convert it to opponent's coordinates
        last_position_opponent = convert_coordinates(last_position)
        num_checkers = fake_board.num_checkers_after_position(
            opponent_color, last_position_opponent
        )

        if num_checkers == 0:
            return False
    else:
        return True


def is_single_move_legal(board: Board, move: SingleMove):
    """
    checks if move can be legally made
    0. move is possible
    1. not blocking 6 in a row (unless there's a checker in front)
    2. bearing off only allowed if all are ot home
    """
    try:
        assert board.is_single_move_possible(move), 'Move is not possible'

        if move.position_to > MAX_POSITION:
            assert board.has_all_checkers_home(
                move.color
            ), 'Cannot bear off until all checkers are home'
    except AssertionError:
        return False
    else:
        return True


def find_single_legal_moves(board: Board, color: str, die_roll: int):
    """
    finds all legal moves for a die roll

    if bearing off, overshooting allowed only if there is no other not-bearing-off move
    """
    # 1. get all possible moves
    moves = board.find_possible_moves(color, die_roll)

    # 2. check basic rules
    moves = [m for m in moves if is_single_move_legal(board, m)]

    # check overshooting bear-off moves (position_to > 25)
    # these moves are only allowed when no non-bear-off moves are left
    # TODO: check this rule
    tray_position = MAX_POSITION + 1

    min_position_to = min([m.position_to for m in moves], default=0)

    # if there are non-bear-off moves - remove all overshooting
    if min_position_to < tray_position:
        moves = [m for m in moves if not m.position_to > tray_position]

    return moves


def find_complete_possible_moves(the_board, dice, color):
    """
    TODO: every move is stored into move cache
    """
    first_roll = dice[0]
    moves = find_single_legal_moves(the_board, color, first_roll)

    # reached last die
    if len(dice) == 1:
        return moves
    else:
        result = []
        for m in moves:
            fake_board = the_board.copy_board()
            fake_board.do_single_move(m)
            rest_of_moves = find_complete_possible_moves(fake_board, dice[1:], color)
            if len(rest_of_moves) == 0:
                result.append([m])
            else:
                for r in rest_of_moves:
                    if type(r) == list:
                        result.append([m, *r])
                    else:
                        result.append([m, r])
        return result


def remove_extra_from_head_moves(
    move: list[SingleMove], allowed_num=1
) -> list[SingleMove]:
    """
    removes single moves that take from head over allowed number
    also need to remove all subsequent moves with that checker
    for example, move 1/6, 1/6, 6/11, 6/11 with allowed_num=1 becomes
    1/6, 6/11
    """
    num_from_head = 0
    filtered_moves = []
    subsequent_slots = []
    for m in move:

        if m.position_from == 1:
            # we haven't reached the limit yet
            if num_from_head < allowed_num:
                filtered_moves.append(m)
            # reached the limit - need to make sure that same checker is not allowed to move further too
            else:
                subsequent_slots.append(m.position_to)

            num_from_head += 1

        # if it's a checker that was removed
        elif m.position_from in subsequent_slots:
            # move should not be considered, mark checker as taken care of
            subsequent_slots.remove(m.position_from)

        # if it's a normal checker and move is not from head - all is ok
        else:
            filtered_moves.append(m)

    return filtered_moves


def is_valid_complete_move(board: Board, moves: list[SingleMove]):
    try:
        fake_board = board.copy_board()
        for m in moves:
            fake_board.do_single_move(m)
    except MoveNotPossibleError:
        return False
    else:
        return True


def find_complete_legal_moves(
    board: Board, color: str, dice_roll: tuple[int, int], filter_moves=True
):
    """
    finds all complete legal moves for dice roll

    4. play both dice when possible
    5. only once from the head per move
    6. if only one die can be played - play second from the head (?)
    7. if only one die can be played - play biggest
    """
    # clear move cache
    init_cache(board)

    # check if double
    def _is_double():
        return dice_roll[0] == dice_roll[1]

    if _is_double():
        dice_roll *= 2

    dice_roll = sorted(dice_roll, reverse=True)

    complete_moves: list[list[SingleMove]] = find_complete_possible_moves(
        board, dice_roll, color
    )

    # if not double, try to start with another die
    if not _is_double():
        reverse_die_moves: list[list[SingleMove]] = find_complete_possible_moves(
            board, dice_roll[::-1], color
        )
        complete_moves += reverse_die_moves

    # 1. first move allows for taking twice from the head
    first_slot = board.get_slot(color, 1)

    # if not first move - take from the head only once
    if first_slot.num_checkers != 15:
        # remove all single moves that take additionally from head
        complete_moves = [remove_extra_from_head_moves(m) for m in complete_moves]

    # allow twice from the head if no other complete move available
    else:
        # remove all single moves that take additionally from head
        once_from_head = [remove_extra_from_head_moves(m) for m in complete_moves]

        # check if still can play all dice
        max_times_move = max([len(m) for m in once_from_head], default=0)
        if max_times_move == len(dice_roll):
            complete_moves = once_from_head
        # if not - only keep moves with up to 2 moves from the head
        else:
            complete_moves = [
                remove_extra_from_head_moves(m, 2) for m in complete_moves
            ]

    # # make sure that reduced moves are  still valid moves
    # complete_moves = [m for m in complete_moves if is_valid_complete_move(m)]

    # 2. not blocking 6 in a row (unless there's a checker in front)
    complete_moves = [m for m in complete_moves if passes_rule_six_block(m)]

    # 3. play both dice when possible
    # filter out moves with incomplete moves
    max_times_move = max([len(m) for m in complete_moves], default=0)
    complete_moves = [m for m in complete_moves if len(m) == max_times_move]

    # 4. if only one die can be played - play biggest
    if max_times_move == 1:
        biggest_die = max(dice_roll)
        complete_moves = [m for m in complete_moves if m[0].length == biggest_die]

    # moves should be filtered to reduce computation complexity
    # but for human player lookups we want all moves, even ifthey result in same
    # board positions. but we still don't need duplicates
    if not filter_moves:
        # remove duplicates
        complete_moves = list(
            complete_moves for complete_moves, _ in itertools.groupby(complete_moves)
        )
    else:
        # remove moves that have duplicated board positions
        lookup = {}
        for m in complete_moves:
            lookup[str(MOVE_BOARD_DICTIONARY[str(m)])] = m

        complete_moves = list(lookup.values())

    return complete_moves


def win_condition(board: Board, color: str):
    """
    checks if any color has won
    """
    if board.num_checkers(color) == 0:
        if board.has_all_checkers_home(Colors.opponent(color)):
            return 1
        else:
            # mars
            return 2
    else:
        return None


def has_won(board, color):
    if board.num_checkers(color) == 0:
        return 0
    else:
        return 1
