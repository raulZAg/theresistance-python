# A rule-based hanabi agent driven by a chromosome.
# The objective of this class is to be a starter-class for a larger set of rules.
# M. Fairbank. November 2021.
from hanabi_learning_environment.rl_env import Agent

def argmax(llist):
    #useful function for arg-max
    return llist.index(max(llist))
    
class MyAgent(Agent):


    def __init__(self, config, chromosome=[5, 1, 10, 4, 7, 14, 7, 11, 3, 12, 14, 2, 8, 6, 13, 15], *args, **kwargs):
        self.chromosome=chromosome
        assert isinstance(chromosome, list)
        
        # Extract max info tokens or set default to 8.
        self.max_information_tokens = config.get('information_tokens', 8)

    def calculate_all_unseen_cards(self, discard_pile, player_hands, fireworks):
        # All of the cards which we can't see are either in our own hand or in the deck.
        # The other cards must be in the discard pile (all cards of which we have seen and remembered) or in other player's hands.
        colors = ['Y', 'B', 'W', 'R', 'G']
        full_hanabi_deck=[{"color":c, "rank":r} for c in colors for r in [0,0,0,1,1,2,2,3,3,4]]
        assert len(full_hanabi_deck)==50 # full hanabi deck size.

        result=full_hanabi_deck
        # subract off all cards that have been discarded...
        for card in discard_pile:
            if card in result:
                result.remove(card)
        
        # subract off all cards that we can see in the other players' hands...
        for hand in player_hands[1:]:
            for card in hand:
                if card in result:
                    result.remove(card)

        for (color, height) in fireworks.items():
            for rank in range(height):
                card={"color":color, "rank":rank}
                if card in result:
                    result.remove(card)

        # Now we left with only the cards we have never seen before in the game (so these are the cards in the deck UNION our own hand).
        return result             

    def filter_card_list_by_hint(self, card_list, hint):
        # This could be enhanced by using negative hint information, available from observation['pyhanabi'].card_knowledge()[player_offset][card_number]
        filtered_card_list=card_list
        if hint["color"]!=None:
            filtered_card_list=[c for c in filtered_card_list if c["color"]==hint["color"]]
        if hint["rank"]!=None:
            filtered_card_list=[c for c in filtered_card_list if c["rank"]==hint["rank"]]
        return filtered_card_list


    def filter_card_list_by_playability(self, card_list, fireworks):
        # find out which cards in card list would fit exactly onto next value of its colour's firework
        return [c for c in card_list if self.is_card_playable(c,fireworks)]

    def filter_card_list_by_unplayable(self, card_list, fireworks):
        # find out which cards in card list are always going to be unplayable on its colour's firework
        # This function could be improved by considering that we know a card of value 5 will never be playable if all the 4s for that colour have been discarded.
        return [c for c in card_list if c["rank"]<fireworks[c["color"]]]

    def is_card_playable(self, card, fireworks):
        return card['rank'] == fireworks[card['color']]

    def calculate_color_cards_left(self, deck_size, discard_pile, fireworks): # This is a function that calculates how many cards of each color are left
        color_cards_left = {'R':deck_size,'G':deck_size,'B':deck_size,'Y':deck_size,'W':deck_size}
        for card in discard_pile:
            color_cards_left[card["color"]] -= 1
        for color in fireworks:
            color_cards_left[color] -= fireworks[color]
        return color_cards_left

    def act(self, observation):
        # this function is called for every player on every turn
        """Act based on an observation."""
        if observation['current_player_offset'] != 0:
            # but only the player with offset 0 is allowed to make an action.  The other players are just observing.
            return None
        
        fireworks = observation['fireworks']
        card_hints=observation['card_knowledge'][0] # This [0] produces the card hints for OUR own hand (player offset 0)
        hand_size=len(card_hints)

        # build some useful lists of information about what we hold in our hand and what team-mates know about their hands.
        all_unseen_cards=self.calculate_all_unseen_cards(observation['discard_pile'],observation['observed_hands'],observation['fireworks'])
        possible_cards_by_hand=[self.filter_card_list_by_hint(all_unseen_cards, h) for h in card_hints]
        playable_cards_by_hand=[self.filter_card_list_by_playability(posscards, fireworks) for posscards in possible_cards_by_hand]
        probability_cards_playable=[len(playable_cards_by_hand[index])/len(possible_cards_by_hand[index]) for index in range(hand_size)]
        useless_cards_by_hand=[self.filter_card_list_by_unplayable(posscards, fireworks) for posscards in possible_cards_by_hand]
        probability_cards_useless=[len(useless_cards_by_hand[index])/len(possible_cards_by_hand[index]) for index in range(hand_size)]
        
        # based on the above calculations, try a sequence of rules in turn and perform the first one that is applicable:
        
        for rule in self.chromosome:
            if rule in [0,1]:
                # Play any highly-probable playable cards:
                threshold=0.8 if rule==0 else 0.5
                if max(probability_cards_playable)>threshold:
                    card_index=argmax(probability_cards_playable)
                    return {'action_type': 'PLAY', 'card_index': card_index}

            elif rule==2:
                # Check if it's possible to hint a card to your colleagues.
                if observation['information_tokens'] > 0:
                    # Check if there are any playable cards in the hands of the opponents.
                    for player_offset in range(1, observation['num_players']):
                        player_hand = observation['observed_hands'][player_offset]
                        player_hints = observation['card_knowledge'][player_offset]
                        # Check if the card in the hand of the opponent is playable.
                        for card, hint in zip(player_hand, player_hints):
                            #if card['rank'] == fireworks[card['color']]:
                            if self.is_card_playable(card,fireworks):
                                if hint['color'] is None:
                                    return {
                                        'action_type': 'REVEAL_COLOR',
                                        'color': card['color'],
                                        'target_offset': player_offset
                                    }
                                elif hint['rank'] is None:
                                    return {
                                        'action_type': 'REVEAL_RANK',
                                        'rank': card['rank'],
                                        'target_offset': player_offset
                                    }
            elif rule in [3,4]:
                # Discard any highly-probable useless cards
                threshold=0.8 if rule==3 else 0.5
                if observation['information_tokens'] < self.max_information_tokens:
                    if max(probability_cards_useless)>threshold:
                        card_index=argmax(probability_cards_useless)
                        return {'action_type': 'DISCARD', 'card_index': card_index}

            elif rule == 5:
                # Check if there are 3 or more fireworks with 3 or more sequences
                count_fireworks_3_more_seq = sum(1 for _, seq in fireworks.items() if seq >= 3)
                if count_fireworks_3_more_seq >= 3:
                    # Play any highly probable playable cards
                    threshold = 0.8
                    if max(probability_cards_playable) > threshold:
                        card_index = argmax(probability_cards_playable)
                        return {'action_type': 'PLAY', 'card_index': card_index}

            elif rule == 6:
                # Discard any highly-probable useless cards
                threshold=0.8 if rule==3 else 0.5
                if observation['information_tokens'] < self.max_information_tokens:
                    if max(probability_cards_useless)>threshold:
                        card_index=argmax(probability_cards_useless)
                        return {'action_type': 'DISCARD', 'card_index': card_index}

            elif rule == 7:
                # Check if there are colors with few cards left
                color_cards_left = self.calculate_color_cards_left(observation['deck_size'], observation['discard_pile'], observation['fireworks'])
                min_cards_left = min(color_cards_left.values())
                min_colors = [color for color, cards_left in color_cards_left.items() if cards_left == min_cards_left]
                # play any highly-probable playable cards of the color with few cards left
                threshold = 0.8
                for color in min_colors:
                    for i, (card, hint) in enumerate(zip(observation['observed_hands'], card_hints)):
                        if hint["color"] == color and hint["rank"] is not None:
                            if self.is_card_playable({"color": hint["color"], "rank": hint["rank"]}, fireworks) and probability_cards_playable[i] > threshold:
                                return {'action_type': 'PLAY', 'card_index': i}

            elif rule == 8:
                # Check if there are 3 or more fireworks with 3 or more sequences
                count_fireworks_3_more_seq = sum(1 for _, seq in fireworks.items() if seq >= 3)
                if count_fireworks_3_more_seq >= 3:
                    # Play any highly-probable playable cards
                    threshold = 0.8
                    if max(probability_cards_playable) > threshold:
                        card_index = argmax(probability_cards_playable)
                        return {'action_type': 'PLAY', 'card_index': card_index}

            elif rule == 9:
                #If there are 1 lives left and less than 3 information tokens left, we discard the most probable useless card
                if observation['life_tokens'] == 1 and observation['information_tokens'] < 3:
                    max_useless_prob = max(probability_cards_useless)
                    if max_useless_prob > 0:
                        card_index = probability_cards_useless.index(max_useless_prob)
                        return {'action_type': 'DISCARD', 'card_index': card_index}

            elif rule == 10:
                #If there are still 3 lives left and less than 3 information tokens, in your turn, you play a card that is probable to be correct
                if observation['life_tokens'] == 3 and observation['information_tokens'] < 3:
                    for i, hint in enumerate(card_hints):
                        if hint['color'] is not None and hint['rank'] is not None:
                            if self.is_card_playable({"color": hint["color"], "rank": hint["rank"]}, fireworks):
                                return {'action_type': 'PLAY', 'card_index': i}

            elif rule == 11:
                # Give a hint about a 1 if any player has a 1 in his deck and there are still fireworks without a one
                if observation['information_tokens'] > 0:
                    for player_offset in range(1, observation['num_players']):
                        player_hand = observation['observed_hands'][player_offset]
                        player_hints = observation['card_knowledge'][player_offset]
                        for card, hint in zip(player_hand, player_hints):
                            if card['rank'] == 1:
                                for color in fireworks:
                                    if fireworks[color] < 1:
                                        if hint['rank'] is None:
                                            return {
                                                'action_type': 'REVEAL_RANK',
                                                'rank': 1,
                                                'target_offset': player_offset
                                            }

            elif rule == 12:
                # Give hints of a color that is higher than 3 in the fireworks pile
                if observation['information_tokens'] > 0:
                    for color in fireworks:
                        if fireworks[color] > 3:
                            for player_offset in range(1, observation['num_players']):
                                player_hand = observation['observed_hands'][player_offset]
                                player_hints = observation['card_knowledge'][player_offset]
                                for card, hint in zip(player_hand, player_hints):
                                    if card['color'] == color:
                                        if hint['color'] is None:
                                            return {
                                                'action_type': 'REVEAL_COLOR',
                                                'color': color,
                                                'target_offset': player_offset
                                            }

            elif rule == 13:
                # Give a hint to a player that already has a hint for a number
                if observation['information_tokens'] > 0:
                    for player_offset in range(1, observation['num_players']):
                        player_hand = observation['observed_hands'][player_offset]
                        player_hints = observation['card_knowledge'][player_offset]
                        for card, hint in zip(player_hand, player_hints):
                            if hint['rank'] is not None and hint['color'] is None:
                                if self.is_card_playable(card, fireworks):
                                    return {
                                        'action_type': 'REVEAL_COLOR',
                                        'color': card['color'],
                                        'target_offset': player_offset
                                    }

            elif rule ==14:
                # Discard something
                if observation['information_tokens'] < self.max_information_tokens:
                    return {'action_type': 'DISCARD', 'card_index': 0}# discards the oldest card (card_index 0 will be oldest card)

            elif rule ==15:
                # Play our best-hope card
                return {'action_type': 'PLAY', 'card_index': argmax(probability_cards_playable)}
            else:
                # the chromosome contains an unknown rule
                raise Exception("Rule not defined: "+str(rule))
        # The chromosome needs to be defined so the program never gets to here.  
        # E.g. always include rules 5 and 6 in the chromosome somewhere to ensure this never happens..        
        raise Exception("No rule fired for game situation - faulty rule set")

